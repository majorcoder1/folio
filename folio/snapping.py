"""Snapping: pull moving objects onto page edges, guides and other objects."""

from PyQt5.QtCore import QPointF


def guide_lines(scene, exclude=(), page=True, objects=True):
    """Return (xs, ys): positions objects should line up with."""
    xs, ys = [], []

    def add_rect(r):
        xs.extend([r.left(), r.center().x(), r.right()])
        ys.extend([r.top(), r.center().y(), r.bottom()])

    doc = scene.doc
    if not page:
        doc = None
    for rect in (doc.regions().values() if doc else ()):
        add_rect(rect)
    if doc is not None:
        for rect in doc.safe_rects():
            xs.extend([rect.left(), rect.right()])
            ys.extend([rect.top(), rect.bottom()])
        for rect in doc.hinge_rects():
            xs.extend([rect.left(), rect.right()])
        barcode = doc.barcode_rect()
        if barcode is not None:
            xs.extend([barcode.left(), barcode.right()])
            ys.extend([barcode.top(), barcode.bottom()])
    if not objects:
        return xs, ys
    skip = set(id(i) for i in exclude)
    for item in scene.folio_items():
        if id(item) in skip or not item.isVisible():
            continue
        add_rect(item.scene_bounds())
    return xs, ys


def _best(values, targets, tol):
    best = None
    for v in values:
        for t in targets:
            d = t - v
            if abs(d) <= tol and (best is None or abs(d) < abs(best[0])):
                best = (d, t)
    return best


def snap_rect(rect, xs, ys, tol):
    """Offset that snaps a moving rectangle, plus the lines it snapped to."""
    bx = _best([rect.left(), rect.center().x(), rect.right()], xs, tol)
    by = _best([rect.top(), rect.center().y(), rect.bottom()], ys, tol)
    dx = bx[0] if bx else 0.0
    dy = by[0] if by else 0.0
    return QPointF(dx, dy), (bx[1] if bx else None), (by[1] if by else None)


def snap_point(p, xs, ys, tol):
    bx = _best([p.x()], xs, tol)
    by = _best([p.y()], ys, tol)
    out = QPointF(p.x() + (bx[0] if bx else 0.0), p.y() + (by[0] if by else 0.0))
    return out, (bx[1] if bx else None), (by[1] if by else None)
