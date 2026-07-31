import { api } from "./client";

// ---- 商品 ----
export interface Product {
  id: string; name: string; sku: string; category: string;
  platform_kbs: { platform: string; platform_name: string; price: string; detail_html: string }[];
}
export const productsApi = {
  list: () => api.get<Product[]>("/products"),
  get: (id: string) => api.get<Product>(`/products/${id}`),
  create: (data: { name: string; sku: string; category?: string }) => api.post<Product>("/products", data),
  delete: (id: string) => api.delete(`/products/${id}`),
  import: (data: { platform: string; url: string; product_id?: string }) => api.post<Product>("/products/import", data),
};

// ---- 视频素材 ----
export interface RawVideo {
  id: string; file_name: string; parse_status: string; parse_progress: number;
  segments: { id: string; start_time: number; end_time: number; script: string; clip_path: string; status: string }[];
}
export const videosApi = {
  list: () => api.get<RawVideo[]>("/video-assets"),
  get: (id: string) => api.get<RawVideo>(`/video-assets/${id}`),
  upload: (form: FormData) => api.upload<RawVideo>("/video-assets/upload", form),
  publishSegment: (id: string) => api.post(`/video-assets/segments/${id}/publish`),
};

// ---- 直播视频 ----
export interface LiveVideoOut {
  id: string; name: string; play_mode: string;
  clips: { id: string; segment_id: string; sort_order: number; weight: number; pause_after: number }[];
}
export const liveVideosApi = {
  list: () => api.get<LiveVideoOut[]>("/live-videos"),
  create: (data: { name: string; play_mode?: string }) => api.post<LiveVideoOut>("/live-videos", data),
  addClip: (videoId: string, data: { segment_id: string; sort_order: number; weight: number; pause_after: number }) =>
    api.post(`/live-videos/${videoId}/clips`, data),
  removeClip: (videoId: string, clipId: string) => api.delete(`/live-videos/${videoId}/clips/${clipId}`),
  reorder: (videoId: string, clipIds: string[]) => api.put(`/live-videos/${videoId}/clips/reorder`, clipIds),
};

// ---- 直播间 ----
export interface RoomOut {
  id: string; name: string; platform: string; rtmp_url: string; status: string; attached_video_id: string | null;
}
export const roomsApi = {
  list: () => api.get<RoomOut[]>("/live-rooms"),
  create: (data: { name: string; platform: string; rtmp_url: string }) => api.post<RoomOut>("/live-rooms", data),
  attach: (roomId: string, videoId: string) => api.post(`/live-rooms/${roomId}/attach/${videoId}`),
  start: (roomId: string) => api.post<RoomOut>(`/live-rooms/${roomId}/start`),
  stop: (roomId: string) => api.post<RoomOut>(`/live-rooms/${roomId}/stop`),
  delete: (roomId: string) => api.delete(`/live-rooms/${roomId}`),
  getSchedule: (roomId: string) => api.get(`/live-rooms/${roomId}/schedule`),
  setSchedule: (roomId: string, data: { enabled: boolean; start_time?: string; end_time?: string }) =>
    api.put(`/live-rooms/${roomId}/schedule`, data),
};

// ---- 互动设置 ----
export interface InteractionConfig {
  id: string; reply_mode: string; reply_decision: string; reply_style: string;
  tts_speed: number; tts_volume: number; tts_pitch: number;
}
export const interactionApi = {
  getConfig: () => api.get<InteractionConfig>("/interaction/config"),
  updateConfig: (data: Partial<InteractionConfig>) => api.put<InteractionConfig>("/interaction/config", data),
  listTemplates: () => api.get<any[]>("/interaction/templates"),
  createTemplate: (data: any) => api.post("/interaction/templates", data),
  deleteTemplate: (id: string) => api.delete(`/interaction/templates/${id}`),
};

// ---- 账号 ----
export const accountApi = {
  getMerchant: () => api.get<any>("/account/merchant"),
  listUsers: () => api.get<any[]>("/account/users"),
  createUser: (data: { username: string; role?: string; quota_hours?: number }) => api.post("/account/users", data),
  deleteUser: (id: string) => api.delete(`/account/users/${id}`),
};

// ---- 平台接入 ----
export const platformApi = {
  getCapabilities: () => api.get<any[]>("/platform/capabilities"),
  listConfigs: () => api.get<any[]>("/platform/configs"),
  upsertConfig: (platform: string, data: any) => api.put(`/platform/configs/${platform}`, data),
};

// ---- 设置 ----
export const settingsApi = {
  list: () => api.get<any[]>("/settings"),
  update: (key: string, value: string) => api.put(`/settings/${key}`, { value }),
};
