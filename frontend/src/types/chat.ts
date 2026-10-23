export interface ToolUse {
  id: string;
  name: string;
  args: Record<string, unknown>;
  // Undefined while the tool is still running
  result?: string;
  // Images returned by the tool, as data URLs
  images?: string[];
}

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
  tools?: ToolUse[];
}
