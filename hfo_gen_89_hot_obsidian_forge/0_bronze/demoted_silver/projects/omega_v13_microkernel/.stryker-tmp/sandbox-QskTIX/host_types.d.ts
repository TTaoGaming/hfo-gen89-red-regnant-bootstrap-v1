// @ts-nocheck

export interface HostWindow {
    innerWidth: number;
    innerHeight: number;
    addEventListener(type: string, listener: any): void;
    removeEventListener(type: string, listener: any): void;
    getComputedStyle(el: any): any;
}
export interface HostDocument {
    body: any;
    getElementById(id: string): any;
    createElement(tagName: string): any;
    elementsFromPoint(x: number, y: number): any[];
}
export interface HostAudioContext {
    state: string;
    resume(): Promise<void>;
    createBufferSource(): any;
    destination: any;
}
export interface HostAudioBuffer {}
export interface HostMediaStreamTrack {}
export interface HostWorker {
    postMessage(msg: any): void;
    onmessage: ((ev: any) => void) | null;
    terminate(): void;
}
