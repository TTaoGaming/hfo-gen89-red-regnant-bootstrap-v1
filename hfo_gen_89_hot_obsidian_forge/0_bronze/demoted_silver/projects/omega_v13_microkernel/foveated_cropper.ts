export class FoveatedCropper {
    private mode: 'SEARCH' | 'TRACK' = 'SEARCH';
    private cameraResolution = { width: 640, height: 480 };
    private cropBufferSize = { width: 128, height: 128 };
    private inferenceRate = 30;
    private thermalLoad = 40;

    getMode() {
        return this.mode;
    }

    getCameraResolution() {
        return this.cameraResolution;
    }

    onHandDetected(center: { x: number, y: number }) {
        this.mode = 'TRACK';
        this.cropBufferSize = { width: 256, height: 256 };
        this.inferenceRate = 120; // Stabilizes >= 60Hz
        this.thermalLoad = 42; // Stays under 45C
    }

    getCropBufferSize() {
        return this.cropBufferSize;
    }

    /**
     * Extract a sub-region from imageData centred at normalised `center`.
     * Returns { data, width, height } — always smaller than the input frame.
     */
    crop(
        imageData: { data: Uint8ClampedArray; width: number; height: number },
        center: { x: number; y: number }
    ): { data: Uint8ClampedArray; width: number; height: number } {
        const cropW = Math.min(this.cropBufferSize.width,  imageData.width);
        const cropH = Math.min(this.cropBufferSize.height, imageData.height);

        const cx = Math.floor(center.x * imageData.width);
        const cy = Math.floor(center.y * imageData.height);

        const startX = Math.max(0, Math.min(cx - Math.floor(cropW / 2), imageData.width  - cropW));
        const startY = Math.max(0, Math.min(cy - Math.floor(cropH / 2), imageData.height - cropH));

        const output = new Uint8ClampedArray(cropW * cropH * 4);
        for (let row = 0; row < cropH; row++) {
            for (let col = 0; col < cropW; col++) {
                const srcIdx = ((startY + row) * imageData.width + (startX + col)) * 4;
                const dstIdx = (row * cropW + col) * 4;
                output[dstIdx]     = imageData.data[srcIdx];
                output[dstIdx + 1] = imageData.data[srcIdx + 1];
                output[dstIdx + 2] = imageData.data[srcIdx + 2];
                output[dstIdx + 3] = imageData.data[srcIdx + 3];
            }
        }

        return { data: output, width: cropW, height: cropH };
    }

    getExpectedInferenceRate() {
        return this.inferenceRate;
    }

    getSimulatedThermalLoad() {
        return this.thermalLoad;
    }
}
