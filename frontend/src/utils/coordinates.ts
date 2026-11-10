/**
 * EVIDEXA Canonical Coordinate Transformation Contract
 *
 * Coordinates received from the backend adhere strictly to NORMALIZED_0_1:
 * - Origin (0.0, 0.0): Top-Left corner of the unrotated page.
 * - Horizontal X axis: Increases from left to right ([0.0, 1.0]).
 * - Vertical Y axis: Increases from top to bottom ([0.0, 1.0]).
 * - Rotations are clockwise in increments of 90 degrees: {0, 90, 180, 270}.
 *
 * This module converts normalized coordinates into pixel layout coordinates
 * for the overlay viewport, taking canvas dimensions, zoom, and rotation into account.
 */

export interface NormalizedBoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ViewportDimensions {
  width: number; // Current displayed pixel width of the page canvas
  height: number; // Current displayed pixel height of the page canvas
}

export interface PixelBoundingBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

export type RotationAngle = 0 | 90 | 180 | 270;

/**
 * Validates and sanitizes a normalized bounding box.
 * Returns null if the box is null, undefined, or has invalid non-numeric fields.
 */
export function sanitizeNormalizedBox(
  box?: Partial<NormalizedBoundingBox> | null
): NormalizedBoundingBox | null {
  if (!box || typeof box !== 'object') return null;
  const x = Number(box.x);
  const y = Number(box.y);
  const width = Number(box.width);
  const height = Number(box.height);

  if (isNaN(x) || isNaN(y) || isNaN(width) || isNaN(height)) {
    return null;
  }

  // Reject negative dimensions
  if (width < 0 || height < 0) return null;

  // Clamp within [0, 1] range to safeguard against tiny floating-point rounding
  const clampedX = Math.max(0, Math.min(1, x));
  const clampedY = Math.max(0, Math.min(1, y));
  const clampedW = Math.max(0, Math.min(1 - clampedX, width));
  const clampedH = Math.max(0, Math.min(1 - clampedY, height));

  return {
    x: clampedX,
    y: clampedY,
    width: clampedW,
    height: clampedH,
  };
}

/**
 * Transforms normalized coordinates under a clockwise rotation.
 * Matches python BoundingBox.apply_rotation implementation.
 */
export function rotateNormalizedBox(
  box: NormalizedBoundingBox,
  rotation: RotationAngle
): NormalizedBoundingBox {
  const normRotation = ((rotation % 360 + 360) % 360) as RotationAngle;

  if (normRotation === 0) {
    return { ...box };
  }

  if (normRotation === 90) {
    // 90 deg clockwise: new_x = 1 - (old_y + old_h), new_y = old_x, new_w = old_h, new_h = old_w
    return {
      x: Number(Math.max(0, Math.min(1, 1.0 - (box.y + box.height))).toFixed(6)),
      y: Number(Math.max(0, Math.min(1, box.x)).toFixed(6)),
      width: Number(Math.max(0, Math.min(1, box.height)).toFixed(6)),
      height: Number(Math.max(0, Math.min(1, box.width)).toFixed(6)),
    };
  }

  if (normRotation === 180) {
    // 180 deg: new_x = 1 - (old_x + old_w), new_y = 1 - (old_y + old_h)
    return {
      x: Number(Math.max(0, Math.min(1, 1.0 - (box.x + box.width))).toFixed(6)),
      y: Number(Math.max(0, Math.min(1, 1.0 - (box.y + box.height))).toFixed(6)),
      width: Number(Math.max(0, Math.min(1, box.width)).toFixed(6)),
      height: Number(Math.max(0, Math.min(1, box.height)).toFixed(6)),
    };
  }

  if (normRotation === 270) {
    // 270 deg clockwise: new_x = old_y, new_y = 1 - (old_x + old_w)
    return {
      x: Number(Math.max(0, Math.min(1, box.y)).toFixed(6)),
      y: Number(Math.max(0, Math.min(1, 1.0 - (box.x + box.width))).toFixed(6)),
      width: Number(Math.max(0, Math.min(1, box.height)).toFixed(6)),
      height: Number(Math.max(0, Math.min(1, box.width)).toFixed(6)),
    };
  }

  return { ...box };
}

/**
 * Projects a canonical normalized bounding box onto displayed viewport pixels.
 *
 * @param box Canonical normalized bounding box in unrotated space
 * @param viewport Dimensions of the rendered display container (in pixels)
 * @param rotation Additional viewing rotation applied to the display
 */
export function normalizedToPixelBox(
  box: NormalizedBoundingBox,
  viewport: ViewportDimensions,
  rotation: RotationAngle = 0
): PixelBoundingBox {
  const rotated = rotateNormalizedBox(box, rotation);

  return {
    left: Math.round(rotated.x * viewport.width),
    top: Math.round(rotated.y * viewport.height),
    width: Math.max(1, Math.round(rotated.width * viewport.width)),
    height: Math.max(1, Math.round(rotated.height * viewport.height)),
  };
}

/**
 * Format a bounding box as a compact string for tooltip display.
 */
export function formatBoxLabel(box: NormalizedBoundingBox): string {
  return `[${(box.x * 100).toFixed(1)}%, ${(box.y * 100).toFixed(1)}%] ${((box.width) * 100).toFixed(1)}% × ${((box.height) * 100).toFixed(1)}%`;
}

