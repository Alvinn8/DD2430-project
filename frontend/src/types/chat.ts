export interface Message {
  id: number;
  text: string;
  sender: "user" | "bot";
  timestamp: Date;
  attachments?: Array<{
    name: string;
    type: string;
    previewUrl?: string;
    contentUrl?: string;
  }>;
}
