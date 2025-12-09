/**
 * TypeScript Type Definitions
 */

// DXF関連
export interface EntityInfo {
    handle: string;
    entity_type: string;
    layer: string;
    color: number;
    color_name: string;
    color_hex: string;
    text?: string;
    position?: [number, number];
    start?: [number, number];
    end?: [number, number];
    center?: [number, number];
    radius?: number;
}

export interface LayerInfo {
    name: string;
    color: number;
    color_name: string;
    entity_count: number;
}

export interface ColorInfo {
    aci: number;
    name: string;
    hex: string;
    count: number;
}

export interface DxfInfo {
    session_id: string;
    filename: string;
    entity_count: number;
    layers: LayerInfo[];
    colors_used: ColorInfo[];
}

export interface OperationCommand {
    operation: string;
    params: Record<string, unknown>;
    confidence: number;
    explanation: string;
}

export interface OperationResult {
    success: boolean;
    affected_count: number;
    message: string;
    preview_svg?: string;
}

export interface PartInfo {
    part_name: string;
    text_handle: string;
    linked_count: number;
    confidence: number;
    linked_handles?: string[];
    center?: [number, number];
}

export interface InterpretResponse {
    success: boolean;
    commands: OperationCommand[];
    message: string;
    used_ai: boolean;
}

// アプリケーション状態
export type AppState =
    | 'initial'
    | 'loading'
    | 'ready'
    | 'previewing'
    | 'executing'
    | 'error';
