"""Copy-Move forgery detection algorithms using ORB keypoints and spatial displacement clustering.

Fast, thread-safe, CPU-first classical computer vision without deep learning dependencies.
Identifies cloned and relocated visual regions within the same document page.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from document_intelligence.domain.enums import CoordinateSystem
from document_intelligence.domain.models.bounding_box import BoundingBox, PageGeometry


@dataclass(frozen=True)
class CopyMoveCluster:
    """Clustered copy-move region pair with spatial displacement."""

    source_box: BoundingBox
    duplicate_box: BoundingBox
    source_pixel_bbox: tuple[int, int, int, int]  # (x, y, w, h)
    duplicate_pixel_bbox: tuple[int, int, int, int]  # (x, y, w, h)
    displacement_dx: float
    displacement_dy: float
    matched_keypoints_count: int


@dataclass
class CopyMovePageResult:
    """Detection results for a single page."""

    page_number: int
    clusters: list[CopyMoveCluster] = field(default_factory=list)
    total_keypoints: int = 0
    total_candidate_matches: int = 0
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def detect_copy_move_clusters(
    image: Image.Image,
    page_geometry: PageGeometry,
    pixel_width: int,
    pixel_height: int,
    max_features: int = 2500,
    min_spatial_distance_px: float = 50.0,
    max_hamming_distance: int = 35,
    ratio_threshold: float = 0.75,
    min_cluster_matches: int = 10,
    displacement_bin_size: float = 30.0,
    min_patch_size_px: int = 18,
) -> tuple[int, int, list[CopyMoveCluster], list[tuple[np.ndarray, np.ndarray]]]:
    """Detect copy-move candidate clusters using ORB features and displacement binning.

    Returns:
        (total_keypoints, total_candidate_matches, clusters, matched_point_pairs)
    """
    # Convert PIL Image to grayscale numpy array
    rgb_np = np.asarray(image)
    if len(rgb_np.shape) == 3:
        gray = cv2.cvtColor(rgb_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = rgb_np

    # Feature extraction with ORB
    orb = cv2.ORB_create(nfeatures=max_features)  # type: ignore[attr-defined]
    keypoints, descriptors = orb.detectAndCompute(gray, None)

    if descriptors is None or len(keypoints) < 10:
        return len(keypoints) if keypoints else 0, 0, [], []

    # KNN matching on descriptors (Hamming distance)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(descriptors, descriptors, k=5)

    valid_pairs: list[tuple[cv2.KeyPoint, cv2.KeyPoint, float, float]] = []
    bins: dict[tuple[int, int], list[tuple[cv2.KeyPoint, cv2.KeyPoint]]] = defaultdict(list)

    for match_group in matches:
        if len(match_group) < 3:
            continue

        # match_group[0] is self-match (distance 0).
        # match_group[1] is best non-self match, match_group[2] is second-best match.
        m1 = match_group[1]
        m2 = match_group[2]

        if m1.queryIdx >= m1.trainIdx:
            continue

        pt1 = keypoints[m1.queryIdx].pt
        pt2 = keypoints[m1.trainIdx].pt

        # Canonical spatial ordering: ensure p1 is top-left, p2 is bottom-right
        if (pt1[0], pt1[1]) > (pt2[0], pt2[1]):
            kp1 = keypoints[m1.trainIdx]
            kp2 = keypoints[m1.queryIdx]
        else:
            kp1 = keypoints[m1.queryIdx]
            kp2 = keypoints[m1.trainIdx]

        dx = kp2.pt[0] - kp1.pt[0]
        dy = kp2.pt[1] - kp1.pt[1]
        dist = math.hypot(dx, dy)

        # Spatial filter: reject close points within the same symbol/character
        if dist < min_spatial_distance_px:
            continue

        # Quality filter: strict Hamming ceiling and Lowe's ratio test
        if m1.distance > max_hamming_distance:
            continue
        if m2.distance > 0 and (m1.distance / m2.distance) > ratio_threshold:
            continue

        valid_pairs.append((kp1, kp2, dx, dy))
        bin_x = int(round(dx / displacement_bin_size))
        bin_y = int(round(dy / displacement_bin_size))
        bins[(bin_x, bin_y)].append((kp1, kp2))

    clusters: list[CopyMoveCluster] = []
    matched_point_pairs: list[tuple[np.ndarray, np.ndarray]] = []

    for (_bx, _by), pair_list in bins.items():
        if len(pair_list) < min_cluster_matches:
            continue

        src_pts = np.array([p[0].pt for p in pair_list], dtype=np.float32)
        dst_pts = np.array([p[1].pt for p in pair_list], dtype=np.float32)

        s_w_raw = float(np.max(src_pts[:, 0]) - np.min(src_pts[:, 0]))
        s_h_raw = float(np.max(src_pts[:, 1]) - np.min(src_pts[:, 1]))
        d_w_raw = float(np.max(dst_pts[:, 0]) - np.min(dst_pts[:, 0]))
        d_h_raw = float(np.max(dst_pts[:, 1]) - np.min(dst_pts[:, 1]))

        # Filter out 1D colinear points (e.g. single horizontal lines of identical font letters)
        if min(s_w_raw, s_h_raw, d_w_raw, d_h_raw) < min_patch_size_px:
            continue

        # Average displacement
        mean_dx = float(np.mean(dst_pts[:, 0] - src_pts[:, 0]))
        mean_dy = float(np.mean(dst_pts[:, 1] - src_pts[:, 1]))

        # Calculate bounding boxes in pixel space with padding
        pad_x = 10
        pad_y = 10

        s_x_min = max(0, int(np.min(src_pts[:, 0])) - pad_x)
        s_y_min = max(0, int(np.min(src_pts[:, 1])) - pad_y)
        s_x_max = min(pixel_width, int(np.max(src_pts[:, 0])) + pad_x)
        s_y_max = min(pixel_height, int(np.max(src_pts[:, 1])) + pad_y)
        s_w = max(1, s_x_max - s_x_min)
        s_h = max(1, s_y_max - s_y_min)

        d_x_min = max(0, int(np.min(dst_pts[:, 0])) - pad_x)
        d_y_min = max(0, int(np.min(dst_pts[:, 1])) - pad_y)
        d_x_max = min(pixel_width, int(np.max(dst_pts[:, 0])) + pad_x)
        d_y_max = min(pixel_height, int(np.max(dst_pts[:, 1])) + pad_y)
        d_w = max(1, d_x_max - d_x_min)
        d_h = max(1, d_y_max - d_y_min)

        # Calculate normalized coordinates without silent clamping
        src_norm_x = s_x_min / pixel_width
        src_norm_y = s_y_min / pixel_height
        src_norm_w = s_w / pixel_width
        src_norm_h = s_h / pixel_height

        dst_norm_x = d_x_min / pixel_width
        dst_norm_y = d_y_min / pixel_height
        dst_norm_w = d_w / pixel_width
        dst_norm_h = d_h / pixel_height

        tolerance = 1e-5
        for name, nx, ny, nw, nh in [
            ("source", src_norm_x, src_norm_y, src_norm_w, src_norm_h),
            ("duplicate", dst_norm_x, dst_norm_y, dst_norm_w, dst_norm_h),
        ]:
            if (
                nx < -tolerance
                or ny < -tolerance
                or (nx + nw) > 1.0 + tolerance
                or (ny + nh) > 1.0 + tolerance
            ):
                raise ValueError(
                    f"Copy-move {name} region extends out of canonical page bounds: x={nx}, y={ny}, w={nw}, h={nh}"
                )

        src_box = BoundingBox(
            x=round(max(0.0, min(1.0, src_norm_x)), 6),
            y=round(max(0.0, min(1.0, src_norm_y)), 6),
            width=round(max(0.0, min(1.0 - src_norm_x, src_norm_w)), 6),
            height=round(max(0.0, min(1.0 - src_norm_y, src_norm_h)), 6),
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )

        dst_box = BoundingBox(
            x=round(max(0.0, min(1.0, dst_norm_x)), 6),
            y=round(max(0.0, min(1.0, dst_norm_y)), 6),
            width=round(max(0.0, min(1.0 - dst_norm_x, dst_norm_w)), 6),
            height=round(max(0.0, min(1.0 - dst_norm_y, dst_norm_h)), 6),
            coordinate_system=CoordinateSystem.NORMALIZED_0_1,
        )

        clusters.append(
            CopyMoveCluster(
                source_box=src_box,
                duplicate_box=dst_box,
                source_pixel_bbox=(s_x_min, s_y_min, s_w, s_h),
                duplicate_pixel_bbox=(d_x_min, d_y_min, d_w, d_h),
                displacement_dx=round(mean_dx, 2),
                displacement_dy=round(mean_dy, 2),
                matched_keypoints_count=len(pair_list),
            )
        )

        for p1, p2 in pair_list:
            matched_point_pairs.append((np.array(p1.pt), np.array(p2.pt)))

    return len(keypoints), len(valid_pairs), clusters, matched_point_pairs


def generate_copy_move_visualization_bytes(
    image: Image.Image,
    clusters: list[CopyMoveCluster],
    matched_pairs: list[tuple[np.ndarray, np.ndarray]],
) -> bytes:
    """Generate encoded PNG bytes for copy-move visualization."""
    vis_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # Draw match connection lines
    for pt1, pt2 in matched_pairs:
        p1 = (int(pt1[0]), int(pt1[1]))
        p2 = (int(pt2[0]), int(pt2[1]))
        cv2.line(vis_bgr, p1, p2, (0, 255, 255), 1)  # Yellow line
        cv2.circle(vis_bgr, p1, 3, (0, 0, 255), -1)  # Red circle at source
        cv2.circle(vis_bgr, p2, 3, (255, 0, 0), -1)  # Blue circle at destination

    # Draw bounding boxes for clusters
    for cluster in clusters:
        sx, sy, sw, sh = cluster.source_pixel_bbox
        dx, dy, dw, dh = cluster.duplicate_pixel_bbox

        # Source box in Green
        cv2.rectangle(vis_bgr, (sx, sy), (sx + sw, sy + sh), (0, 255, 0), 2)
        cv2.putText(
            vis_bgr, "Source", (sx, max(15, sy - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
        )

        # Duplicate box in Magenta/Red
        cv2.rectangle(vis_bgr, (dx, dy), (dx + dw, dy + dh), (0, 0, 255), 2)
        cv2.putText(
            vis_bgr,
            "Duplicate",
            (dx, max(15, dy - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
        )

    success, encoded = cv2.imencode(".png", vis_bgr)
    if not success:
        raise ValueError("Failed to encode copy-move visualization to PNG format.")
    return bytes(encoded)


def save_copy_move_visualization(
    image: Image.Image,
    clusters: list[CopyMoveCluster],
    matched_pairs: list[tuple[np.ndarray, np.ndarray]],
    output_path: Path,
) -> Path:
    """Save an annotated image highlighting source and duplicate regions connected by match lines."""
    data = generate_copy_move_visualization_bytes(image, clusters, matched_pairs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path
