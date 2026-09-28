"""Standardize DSC data files into linked data and metadata CSV files."""

from __future__ import annotations

import csv
import math
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR if (SCRIPT_DIR / "data").is_dir() else SCRIPT_DIR.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "standardized_data"
DATA_COLUMNS = ["time_min", "temperature_C", "heat_flow_mW"]
EXCEL_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


@dataclass
class Trace:
    sample_name: str
    rows: list[tuple[Optional[float], Optional[float], Optional[float]]]
    mass_mg: Optional[float] = None
    heating_rate: Optional[float] = None
    source_signal: str = ""
    source_unit: str = ""
    notes: list[str] = field(default_factory=list)
    suffix: str = ""


def read_text(path: Path) -> str:
    """Read common DSC text encodings without changing the source file."""
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be")
    if len(raw) % 2 == 0 and raw:
        even_nulls = raw[0::2].count(0)
        odd_nulls = raw[1::2].count(0)
        if max(even_nulls, odd_nulls) > len(raw) // 8:
            encoding = "utf-16-le" if odd_nulls > even_nulls else "utf-16-be"
            return raw.decode(encoding)
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Could not decode {path}")


def number(value: object) -> Optional[float]:
    text = str(value).strip().replace("\u2212", "-")
    if not text or text.lower() in {"--", "-", "nan", "n/a", "na", "null"}:
        return None
    text = text.replace(" ", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        result = float(text)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def clean_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def extract_mass(text: str) -> Optional[float]:
    patterns = (
        r"(?:sample\s*(?:weight|mass)|mass|size)\s*[:=]?\s*([\d.,]+)\s*(?:\[\s*)?mg",
        r"(?:sample\s*(?:weight|mass)|mass|size)\s*[:=]?\s*([\d.,]+)\s*mg",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return number(match.group(1))
    return None


def extract_heating_rate(text: str) -> tuple[Optional[float], list[float]]:
    rates = [number(match) for match in re.findall(
        r"(?:ramp\s+|temp\s+rate\s+)([\d.,]+)\s*(?:\u00b0\s*)?c\s*/\s*min",
        text,
        re.IGNORECASE,
    )]
    rates = [rate for rate in rates if rate is not None]
    unique = sorted(set(rates))
    return (unique[0] if len(unique) == 1 else None), unique


def convert_heat_flow(value: Optional[float], unit: str, mass_mg: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    normalized = unit.lower().replace(" ", "").replace("^", "")
    if normalized in {"mw", "milliwatt", "milliwatts"}:
        return value
    if normalized in {"w/g", "wg-1", "w*g-1", "w/g^-1"} and mass_mg is not None:
        return value * mass_mg
    return None


def make_trace(
    sample: str,
    raw_rows: list[tuple[Optional[float], Optional[float], Optional[float]]],
    *,
    mass_mg: Optional[float],
    heating_rate: Optional[float],
    signal: str,
    unit: str,
    time_scale: float = 1.0,
    suffix: str = "",
) -> Trace:
    rows = [(time * time_scale if time is not None else None, temp,
             convert_heat_flow(heat, unit, mass_mg))
            for time, temp, heat in raw_rows]
    notes = []
    if any(time is None for time, _, _ in rows):
        notes.append("Time was not present in the source; time_min is blank.")
    normalized_unit = unit.lower().replace(" ", "").replace("^", "")
    if normalized_unit in {"w/g", "wg-1", "w*g-1"} and mass_mg is None:
        notes.append("Source heat flow is W/g but sample mass is unavailable; heat_flow_mW is blank.")
    elif any(heat is not None and converted is None for (_, _, heat), (_, _, converted) in zip(raw_rows, rows)):
        notes.append(f"Source heat-flow unit {unit!r} could not be converted to mW; heat_flow_mW is blank.")
    if heating_rate is None:
        notes.append("Heating rate was not found in the method metadata.")
    return Trace(sample, rows, mass_mg, heating_rate, signal, unit, notes, suffix)


def parse_q2000(path: Path, text: str) -> list[Trace]:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().lower() == "startofdata"), None)
    if start is None:
        raise ValueError("Missing StartOfData marker")
    fields: dict[str, str] = {}
    for line in lines[:start]:
        parts = re.split(r"\t+|\s{2,}", line.strip(), maxsplit=1)
        if len(parts) == 2:
            fields[parts[0].strip().lower()] = parts[1].strip()
    sample = fields.get("sample") or path.stem
    size_match = re.search(r"([\d.,]+)\s*mg", fields.get("size", ""), re.IGNORECASE)
    mass = number(size_match.group(1)) if size_match else extract_mass("\n".join(lines[:start]))
    rate, rates = extract_heating_rate("\n".join(lines[:start]))
    rows = []
    for line in lines[start + 1:]:
        values = re.split(r"\s+", line.strip())
        if len(values) >= 3:
            parsed = [number(value) for value in values[:3]]
            if all(value is not None for value in parsed):
                rows.append((parsed[0], parsed[1], parsed[2]))
    if not rows:
        raise ValueError("No numeric rows found after StartOfData")
    trace = make_trace(sample, rows, mass_mg=mass, heating_rate=rate,
                       signal="Heat Flow", unit="mW")
    if len(rates) > 1:
        trace.notes.append("Method contains multiple heating rates: " + ", ".join(map(str, rates)) + ".")
    return [trace]


def parse_mannitol(path: Path, text: str) -> list[Trace]:
    lines = text.splitlines()
    data_start = next((i for i, line in enumerate(lines) if line.strip().lower() == "[data]"), None)
    if data_start is None:
        raise ValueError("Missing [Data] section")
    mass = extract_mass("\n".join(lines[:data_start]))
    method_text = "\n".join(lines[:data_start])
    rate_values = []
    in_program = False
    for line in lines[:data_start]:
        if line.strip().lower() == "[temp program]":
            in_program = True
            continue
        if in_program:
            values = line.split()
            if len(values) >= 4 and number(values[0]) is not None:
                rate_values.append(number(values[0]))
    unique_rates = sorted(set(rate for rate in rate_values if rate is not None))
    rate = unique_rates[0] if len(unique_rates) == 1 else None
    header_index = next((i for i in range(data_start + 1, len(lines))
                         if re.search(r"\btime\b", lines[i], re.IGNORECASE)
                         and re.search(r"\btemp\b", lines[i], re.IGNORECASE)), None)
    if header_index is None:
        raise ValueError("Missing Time/Temp/DSC data columns")
    rows = []
    for line in lines[header_index + 1:]:
        values = line.split()
        if len(values) < 3:
            continue
        time, temp, heat = (number(value) for value in values[:3])
        if time is not None and temp is not None:
            rows.append((time, temp, heat))
    if not rows:
        raise ValueError("No numeric data rows found")
    trace = make_trace(path.parent.name, rows, mass_mg=mass, heating_rate=rate,
                       signal="DSC", unit="mW", time_scale=1 / 60)
    if len(unique_rates) > 1:
        trace.notes.append("Method contains multiple heating rates: " + ", ".join(map(str, unique_rates)) + ".")
    return [trace]


def parse_delimited(path: Path, text: str) -> list[Trace]:
    csv.field_size_limit(10_000_000)
    lines = text.splitlines()
    nonempty = [line for line in lines if line.strip()]
    if not nonempty:
        raise ValueError("Empty input file")
    sample_rows = nonempty[:12]
    delimiter = max((";", "\t", ","), key=lambda candidate: sum(line.count(candidate) for line in sample_rows))
    records = list(csv.reader(lines, delimiter=delimiter))
    header_index = next((i for i, row in enumerate(records)
                         if any("temperature" in clean_header(cell) for cell in row)
                         and any("heat flow" in clean_header(cell) for cell in row)), None)
    if header_index is None:
        raise ValueError("Could not locate temperature and heat-flow columns")
    headers = [clean_header(cell) for cell in records[header_index]]
    units = [cell.strip() for cell in records[header_index + 1]] if header_index + 1 < len(records) else []

    def find_column(candidates: tuple[str, ...]) -> Optional[int]:
        return next((i for i, header in enumerate(headers) if header in candidates), None)

    time_col = find_column(("time",))
    temp_col = find_column(("temperature",))
    mod_temp_col = find_column(("modulated temperature",))
    flow_col = find_column(("modulated heat flow",))
    flow_label = "Modulated Heat Flow"
    if flow_col is None:
        flow_col = next((i for i, header in enumerate(headers)
                         if "heat flow" in header and i < len(units)
                         and units[i].strip().lower() in {"mw", "w/g", "wg^-1"}), None)
        flow_label = headers[flow_col] if flow_col is not None else ""
    if flow_col is None:
        raise ValueError("No heat-flow column found")
    temp_index = temp_col if temp_col is not None else mod_temp_col
    if temp_index is None:
        raise ValueError("No temperature column found")
    unit = units[flow_col].strip().strip("[]") if flow_col < len(units) else ""
    time_unit = units[time_col].strip().lower() if time_col is not None and time_col < len(units) else "min"
    time_scale = 1 / 60 if time_unit.startswith("sec") else 1.0
    mass = extract_mass(text[:sum(len(line) + 1 for line in lines[:header_index])])
    rate, rates = extract_heating_rate(text)
    raw_rows = []
    for record in records[header_index + 1:]:
        if len(record) <= max(flow_col, temp_index, time_col or 0):
            continue
        time = number(record[time_col]) if time_col is not None and time_col < len(record) else None
        temperature = number(record[temp_index])
        if temperature is None and mod_temp_col is not None and mod_temp_col < len(record):
            temperature = number(record[mod_temp_col])
        heat = number(record[flow_col])
        if time is not None or temperature is not None or heat is not None:
            raw_rows.append((time, temperature, heat))
    if not raw_rows:
        raise ValueError("No data rows found")
    trace = make_trace(path.stem, raw_rows, mass_mg=mass, heating_rate=rate,
                       signal=flow_label, unit=unit, time_scale=time_scale)
    if len(rates) > 1:
        trace.notes.append("Method contains multiple heating rates: " + ", ".join(map(str, rates)) + ".")
    return [trace]


def parse_bosentan(text: str, path: Path) -> list[Trace]:
    lines = text.splitlines()
    if len(lines) < 3:
        raise ValueError("Expected column headers, units, and numeric data")
    unit_line = lines[1]
    unit_match = re.search(r"\[\s*(W\s*g\s*\^?-?1|mW)\s*\]", unit_line, re.IGNORECASE)
    unit = unit_match.group(1).replace(" ", "") if unit_match else ""
    mass = extract_mass("\n".join(lines[:2]))
    rate = 5.0
    channels: list[list[tuple[Optional[float], Optional[float], Optional[float]]]] = [[], [], []]
    for line in lines[2:]:
        values = re.split(r"\s+", line.strip())
        if len(values) < 4:
            continue
        temperature = number(values[0])
        if temperature is None:
            continue
        for index, channel in enumerate(channels):
            channel.append((None, temperature, number(values[index + 1])))
    traces = []
    for index, rows in enumerate(channels, start=1):
        if rows:
            trace = make_trace(path.stem, rows, mass_mg=mass, heating_rate=rate,
                               signal=f"signal_{index}", unit=unit,
                               suffix=f"signal_{index}")
            trace.notes.append(
                "Heating rate 5 C/min reported in the Mendeley dataset methods "
                "(https://data.mendeley.com/datasets/t8z4nhv2j7/1); sample mass was not reported."
            )
            traces.append(trace)
    if not traces:
        raise ValueError("No numeric temperature/heat-flow rows found")
    return traces


def xlsx_cell_text(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    value = cell.find(f"{{{EXCEL_NS}}}v")
    if value is None:
        inline = cell.find(f"{{{EXCEL_NS}}}is")
        return "".join(node.text or "" for node in inline.iter(f"{{{EXCEL_NS}}}t")) if inline is not None else ""
    text = value.text or ""
    if cell.attrib.get("t") == "s":
        return shared_strings[int(text)]
    return text


def column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return 0
    result = 0
    for char in letters.group(0):
        result = result * 26 + ord(char) - ord("A") + 1
    return result - 1


def parse_xlsx(path: Path) -> list[Trace]:
    traces = []
    with zipfile.ZipFile(path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {element.attrib["Id"]: element.attrib["Target"]
                   for element in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship")}
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            string_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = ["".join(node.text or "" for node in item.iter(f"{{{EXCEL_NS}}}t"))
                              for item in string_root.findall(f"{{{EXCEL_NS}}}si")]
        for sheet in workbook.findall(f"{{{EXCEL_NS}}}sheets/{{{EXCEL_NS}}}sheet"):
            target = targets[sheet.attrib[f"{{{REL_NS}}}id"]].lstrip("/")
            if not target.startswith("xl/"):
                target = posixpath.normpath(posixpath.join("xl", target))
            sheet_root = ElementTree.fromstring(archive.read(target))
            xml_rows = sheet_root.findall(f".//{{{EXCEL_NS}}}sheetData/{{{EXCEL_NS}}}row")
            grid = []
            for xml_row in xml_rows:
                row = {}
                for cell in xml_row.findall(f"{{{EXCEL_NS}}}c"):
                    row[column_index(cell.attrib.get("r", ""))] = xlsx_cell_text(cell, shared_strings)
                grid.append(row)
            for header_index, header_row in enumerate(grid):
                temp_col = next((i for i, value in header_row.items() if "temperature" in clean_header(value)), None)
                flow_header = next((value for value in header_row.values() if "heat flow" in clean_header(value)), "")
                if temp_col is None or not flow_header:
                    continue
                labels = grid[header_index + 1] if header_index + 1 < len(grid) else {}
                unit_match = re.search(r"\(([^)]+)\)", flow_header)
                unit = unit_match.group(1).strip() if unit_match else ""
                for flow_col, label in labels.items():
                    if flow_col == temp_col or not label.strip():
                        continue
                    raw_rows = []
                    for row in grid[header_index + 2:]:
                        temperature = number(row.get(temp_col, ""))
                        heat = number(row.get(flow_col, ""))
                        if temperature is not None or heat is not None:
                            raw_rows.append((None, temperature, heat))
                    if raw_rows:
                        slug = re.sub(r"[^A-Za-z0-9_-]+", "_", label.strip()).strip("_")
                        trace = make_trace(label.strip(), raw_rows, mass_mg=10.0,
                                           heating_rate=10.0, signal=label.strip(),
                                           unit=unit, suffix=slug or f"signal_{flow_col + 1}")
                        trace.notes.append(
                            "Approximate sample mass (~10 mg) and heating rate (10 C/min) "
                            "reported in the DSC methods (https://doi.org/10.1007/s40268-026-00546-9); "
                            "heat_flow_mW is approximate because the reported mass is approximate."
                        )
                        traces.append(trace)
                break
    if not traces:
        raise ValueError("No worksheet with a temperature and heat-flow table was found")
    return traces


def write_trace(source: Path, medicine_dir: Path, trace: Trace) -> tuple[Path, Path]:
    relative_parent = source.parent.relative_to(medicine_dir)
    output_parent = OUTPUT_DIR / medicine_dir.name / relative_parent
    output_parent.mkdir(parents=True, exist_ok=True)
    suffix = f"__{trace.suffix}" if trace.suffix else ""
    data_path = output_parent / f"{source.stem}{suffix}.csv"
    metadata_path = output_parent / f"{source.stem}{suffix}_metadata.csv"
    with data_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(DATA_COLUMNS)
        writer.writerows(trace.rows)
    source_relative = source.relative_to(DATA_DIR).as_posix()
    metadata = {
        "source_file": source_relative,
        "data_file": data_path.name,
        "sample_name": trace.sample_name,
        "sample_mass_mg": trace.mass_mg,
        "heating_rate_C_per_min": trace.heating_rate,
        "source_signal": trace.source_signal,
        "source_heat_flow_unit": trace.source_unit,
        "conversion_status": "complete" if all(
            heat is not None for _, _, heat in trace.rows
        ) else "partial_or_unavailable",
        "notes": " ".join(trace.notes),
    }
    with metadata_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(metadata), lineterminator="\n")
        writer.writeheader()
        writer.writerow(metadata)
    return data_path, metadata_path


def standardize() -> None:
    if not DATA_DIR.is_dir():
        raise FileNotFoundError(f"Expected a data directory at {DATA_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    supported = {".txt", ".csv", ".xlsx"}
    converted = 0
    skipped = []
    failed = []
    for medicine_dir in sorted(path for path in DATA_DIR.iterdir() if path.is_dir()):
        for source in sorted(path for path in medicine_dir.rglob("*") if path.is_file()):
            if source.suffix.lower() not in supported:
                skipped.append(source.relative_to(DATA_DIR).as_posix())
                continue
            try:
                if source.suffix.lower() == ".xlsx":
                    traces = parse_xlsx(source)
                else:
                    text = read_text(source)
                    if "[data]" in text.lower() and "[temp program]" in text.lower():
                        traces = parse_mannitol(source, text)
                    elif "startofdata" in text.lower():
                        traces = parse_q2000(source, text)
                    elif source.parent.name.lower() == "bosenthan":
                        traces = parse_bosentan(text, source)
                    else:
                        traces = parse_delimited(source, text)
                for trace in traces:
                    write_trace(source, medicine_dir, trace)
                converted += len(traces)
                print(f"OK {source.relative_to(DATA_DIR)} ({len(traces)} trace(s))")
            except Exception as error:  # Keep processing other experiments after one malformed file.
                failed.append((source.relative_to(DATA_DIR).as_posix(), str(error)))
                print(f"FAILED {source.relative_to(DATA_DIR)}: {error}")
    print(f"\nCreated {converted} standardized trace(s) in {OUTPUT_DIR.relative_to(ROOT)}.")
    if skipped:
        print(f"Skipped {len(skipped)} unsupported file(s), including non-DSC assets.")
    if failed:
        print(f"Could not parse {len(failed)} supported file(s):")
        for relative_path, error in failed:
            print(f"  {relative_path}: {error}")


if __name__ == "__main__":
    standardize()