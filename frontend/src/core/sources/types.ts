export type SourceType = "web_url" | "youtube_video" | "pdf";

export interface Source {
  id: string;
  source_type: SourceType;
  url: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateSourceInput {
  source_type: SourceType;
  url: string;
  description?: string;
  is_active?: boolean;
}

export type UpdateSourceInput = Partial<CreateSourceInput>;
