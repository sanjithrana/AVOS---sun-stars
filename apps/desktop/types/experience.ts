export interface PerformanceMetrics {
  views: number;
  retention_rate: number; // 0.0 to 1.0
  engagement_rate: number; // 0.0 to 1.0
  click_through_rate?: number;
  average_view_duration?: number;
}

export interface VideoExperience {
  experience_id: string;
  project_id: string;
  video_url: string;
  published_at: string;
  platform?: "youtube" | "tiktok" | "instagram" | "internal";
  metrics: PerformanceMetrics;
  retention_curve?: number[]; // Array of retention % at time intervals
  feedback?: {
    user_rating?: number;
    comments?: string[];
  };
  learned_insights: string[];
  created_at: string;
}