package com.pdfstamp;

/**
 * 印章放置位置（PDF坐标系，原点在左下角）
 */
public class StampPosition {
    /** 印章中心点 X 坐标（PDF点单位） */
    public final float cx;
    /** 印章中心点 Y 坐标（PDF点单位） */
    public final float cy;

    public StampPosition(float cx, float cy) {
        this.cx = cx;
        this.cy = cy;
    }

    @Override
    public String toString() {
        return String.format("StampPosition(cx=%.1f, cy=%.1f)", cx, cy);
    }
}
