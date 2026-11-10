import { describe, expect, it } from 'vitest';
import {
  formatBoxLabel,
  normalizedToPixelBox,
  rotateNormalizedBox,
  sanitizeNormalizedBox,
} from '../utils/coordinates';

describe('Coordinate Transformation Contract', () => {
  it('sanitizes valid and invalid bounding boxes', () => {
    expect(sanitizeNormalizedBox(null)).toBeNull();
    expect(sanitizeNormalizedBox(undefined)).toBeNull();
    expect(sanitizeNormalizedBox({ x: NaN, y: 0.1, width: 0.2, height: 0.2 })).toBeNull();
    expect(sanitizeNormalizedBox({ x: 0.1, y: 0.1, width: -0.2, height: 0.2 })).toBeNull();

    const valid = sanitizeNormalizedBox({ x: 0.1, y: 0.2, width: 0.3, height: 0.4 });
    expect(valid).toEqual({ x: 0.1, y: 0.2, width: 0.3, height: 0.4 });

    // Handles slight rounding beyond 1.0 safely
    const overflow = sanitizeNormalizedBox({ x: 0.9, y: 0.9, width: 0.2, height: 0.2 });
    expect(overflow?.x).toBe(0.9);
    expect(overflow?.width).toBeCloseTo(0.1);
  });

  it('transforms bounding box under 90 degree clockwise rotation', () => {
    const box = { x: 0.1, y: 0.2, width: 0.3, height: 0.4 };
    const rotated = rotateNormalizedBox(box, 90);
    // new_x = 1 - (0.2 + 0.4) = 0.4
    // new_y = 0.1
    // new_w = 0.4
    // new_h = 0.3
    expect(rotated.x).toBeCloseTo(0.4);
    expect(rotated.y).toBeCloseTo(0.1);
    expect(rotated.width).toBeCloseTo(0.4);
    expect(rotated.height).toBeCloseTo(0.3);
  });

  it('transforms bounding box under 180 degree rotation', () => {
    const box = { x: 0.1, y: 0.2, width: 0.3, height: 0.4 };
    const rotated = rotateNormalizedBox(box, 180);
    // new_x = 1 - (0.1 + 0.3) = 0.6
    // new_y = 1 - (0.2 + 0.4) = 0.4
    // new_w = 0.3
    // new_h = 0.4
    expect(rotated.x).toBeCloseTo(0.6);
    expect(rotated.y).toBeCloseTo(0.4);
    expect(rotated.width).toBeCloseTo(0.3);
    expect(rotated.height).toBeCloseTo(0.4);
  });

  it('transforms bounding box under 270 degree rotation', () => {
    const box = { x: 0.1, y: 0.2, width: 0.3, height: 0.4 };
    const rotated = rotateNormalizedBox(box, 270);
    // new_x = 0.2
    // new_y = 1 - (0.1 + 0.3) = 0.6
    // new_w = 0.4
    // new_h = 0.3
    expect(rotated.x).toBeCloseTo(0.2);
    expect(rotated.y).toBeCloseTo(0.6);
    expect(rotated.width).toBeCloseTo(0.4);
    expect(rotated.height).toBeCloseTo(0.3);
  });

  it('converts normalized box to pixel coordinates matching viewport and zoom', () => {
    const box = { x: 0.25, y: 0.5, width: 0.5, height: 0.25 };
    const viewport = { width: 800, height: 1000 };

    const pixelBox = normalizedToPixelBox(box, viewport, 0);
    expect(pixelBox).toEqual({
      left: 200,
      top: 500,
      width: 400,
      height: 250,
    });

    // With 2x zoom (viewport width 1600, height 2000)
    const zoomedPixelBox = normalizedToPixelBox(box, { width: 1600, height: 2000 }, 0);
    expect(zoomedPixelBox).toEqual({
      left: 400,
      top: 1000,
      width: 800,
      height: 500,
    });
  });

  it('formats label correctly', () => {
    const box = { x: 0.123, y: 0.456, width: 0.2, height: 0.1 };
    expect(formatBoxLabel(box)).toBe('[12.3%, 45.6%] 20.0% × 10.0%');
  });
});

