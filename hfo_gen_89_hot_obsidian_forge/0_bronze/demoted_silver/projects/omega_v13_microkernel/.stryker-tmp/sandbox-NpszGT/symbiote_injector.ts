// @ts-nocheck
export class SymbioteInjector {
    private adapterLoaded = true;
    private lastMessage: any = null;

    isAdapterLoaded() { return this.adapterLoaded; }
    getLastReceivedMessage() { return this.lastMessage; }

    receiveHostMessage(msg: any) {
        this.lastMessage = msg;
    }

    translateToLocal(global: { x: number, y: number }, iframeRect: { left: number, top: number }) {
        return {
            x: global.x - iframeRect.left,
            y: global.y - iframeRect.top
        };
    }

    synthesizeEvent(): any {
        if (!this.lastMessage) return null;
        
        const event = {
            type: this.lastMessage.type,
            composed: true,
            clientX: this.lastMessage.clientX,
            clientY: this.lastMessage.clientY,
            getPredictedEvents: () => this.lastMessage.predictedEvents || []
        };
        return event;
    }
}
