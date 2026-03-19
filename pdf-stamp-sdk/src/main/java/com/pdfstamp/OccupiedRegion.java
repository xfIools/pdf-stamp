package com.pdfstamp;

/**
 * 页面上已被占用的矩形区域（含缓冲padding）
 */
public class OccupiedRegion {
    public final float x0, y0, x1, y1;

    public OccupiedRegion(float x0, float y0, float x1, float y1) {
        this.x0 = x0;
        this.y0 = y0;
        this.x1 = x1;
        this.y1 = y1;
    }

    /** 判断给定矩形是否与本区域相交 */
    public boolean intersects(float rx0, float ry0, float rx1, float ry1) {
        return rx0 < x1 && rx1 > x0 && ry0 < y1 && ry1 > y0;
    }
}
