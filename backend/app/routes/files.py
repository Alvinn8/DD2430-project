"""Replacement for app/routes/files.py: upload goes through ingest_file()."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import DSCFile
from app.db.schemas.dsc import DSCMetadataPayload, DSCMetadataRead, FileUploadResponse
from app.db.session import get_db
from app.services.ingest import (
    IngestResult,
    UnsupportedFileError,
    apply_user_metadata,
    ingest_file,
    pair_sidecars,
)

router = APIRouter(prefix="/api/v1/files", tags=["DSC Files"])


def to_response(result: IngestResult) -> FileUploadResponse:
    meta_read = DSCMetadataRead.model_validate(result.metadata)
    return FileUploadResponse(
        file_id=result.db_file.file_id,
        original_filename=result.db_file.original_filename,
        storage_uri=result.db_file.storage_uri,
        metadata=meta_read,
        missing_critical_fields=result.missing_critical_fields,
        ready_for_analysis=result.ready_for_analysis,
        parse_warnings=result.warnings,
        unconfirmed_fields=result.unconfirmed,
    )


@router.post(
    "/upload",
    response_model=list[FileUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_dsc_files(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> list[FileUploadResponse]:
    """Upload one or more DSC files. A `<name>_metadata.csv` is paired with `<name>.*`."""
    named = [(f.filename, await f.read()) for f in files if f.filename]
    if not named:
        raise HTTPException(
            status_code=400, detail="At least one file with a name is required."
        )

    types = {f.filename: f.content_type for f in files}
    groups = pair_sidecars(named)
    if not groups:
        raise HTTPException(
            status_code=400,
            detail="No supported DSC file found (.csv, .txt, .tsv, .dat, .xls, .xlsx).",
        )

    responses = []
    for name, data, sidecar in groups:
        try:
            result = await ingest_file(
                db, data, name, content_type=types.get(name), sidecar_bytes=sidecar
            )
        except UnsupportedFileError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        responses.append(to_response(result))
    return responses


@router.patch("/{file_id}/metadata", response_model=FileUploadResponse)
async def verify_file_metadata(
    file_id: uuid.UUID,
    payload: DSCMetadataPayload,
    db: AsyncSession = Depends(get_db),
) -> FileUploadResponse:
    """Confirm or fill metadata. Only fields present in the request body are changed."""
    db_file = (
        await db.execute(
            select(DSCFile)
            .options(selectinload(DSCFile.metadata_record))
            .where(DSCFile.file_id == file_id)
        )
    ).scalar_one_or_none()
    if not db_file or not db_file.metadata_record:
        raise HTTPException(status_code=404, detail="DSC file or metadata not found.")

    changes = payload.model_dump(exclude_unset=True, exclude={"raw_header_json"})
    result = await apply_user_metadata(db, db_file, changes)
    return to_response(result)
