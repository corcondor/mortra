"""Pixels, and the one place where measurement becomes geometry.

This module is deliberately not MORTRA. It is the layer underneath: a bitmap is
a grid of black and white cells, and everything here is counting, integer
morphology, ordering and rounding. No predicate of the fragment is decided in
this file, and nothing here is offered as a proof of anything.

That separation is the point. A raster image is a measurement, and a measurement
is not exact; if exact geometry is to say anything about an image at all, there
has to be a single, stated place where the inexactness is spent. Here it is
spent in three places and nowhere else:

* thinning, which chooses one pixel-wide representative of a thick stroke;
* the polyline tolerance, which decides how far a chain of pixels may wander
  from a straight line before it counts as a corner;
* the snap grid, which rounds the recovered corners onto a coarse rational
  lattice.

After the snap the coordinates are exact rationals and every geometric question
is handed to the fragment's certifier, which answers it exactly. Before the snap
nothing is claimed.

The rendering direction is different, and worth saying plainly: the black set of
a drawn stroke is
    { X : there is a point Q of the segment with |X - Q| <= r },
and that "<=" is an order, which the equality fragment does not have. What
`geometry_sign` shows is that the order fact can be handed a witness -- the
point Q is the fragment's own `foot`, and "within r" becomes membership of a
disk whose two circle points are constructed -- so every inked cell of every
letter here has a certificate in QQ. The comparison is still what the loop
below runs, because a per-pixel certificate would cost a thousand times more;
the certificate is what the claim rests on, not what the renderer executes.
"""
from __future__ import annotations

from collections import deque
from fractions import Fraction


# ---------------------------------------------------------------------------
# A bitmap
# ---------------------------------------------------------------------------

class Bitmap:
    """Black cells on a white grid, with x to the right and y upward.

    The cell (i, j) is the unit square [i, i+1] x [j, j+1] and its centre is
    (i + 1/2, j + 1/2). That convention is used for rendering and for lifting
    pixels back to points, and it is the only convention in the module.
    """

    __slots__ = ("width", "height", "black")

    def __init__(self, width, height, black=()):
        self.width, self.height = int(width), int(height)
        self.black = set(black)

    def __contains__(self, cell):
        return cell in self.black

    def inside(self, i, j):
        return 0 <= i < self.width and 0 <= j < self.height

    def count(self):
        return len(self.black)

    def bounding_box(self):
        """(xmin, ymin, xmax, ymax) over black cell indices, inclusive."""
        if not self.black:
            return None
        xs = [i for i, _ in self.black]
        ys = [j for _, j in self.black]
        return min(xs), min(ys), max(xs), max(ys)

    def rows(self):
        """Top row first, as strings of '#' and '.'; for eyes and for tests."""
        return ["".join("#" if (i, j) in self.black else "." for i in range(self.width))
                for j in reversed(range(self.height))]

    def __str__(self):
        return "\n".join(self.rows())


NEIGHBOURS_8 = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
NEIGHBOURS_4 = ((1, 0), (0, 1), (-1, 0), (0, -1))


# ---------------------------------------------------------------------------
# Drawing: the r-neighbourhood of a set of segments, sampled on the grid
# ---------------------------------------------------------------------------

def _squared_distance_to_segment(point, a, b):
    """|X - Q|^2 minimised over Q on the closed segment AB, exactly."""
    px, py = point
    ax, ay = a
    bx, by = b
    dx, dy = bx-ax, by-ay
    if dx == 0 and dy == 0:
        return (px-ax)**2+(py-ay)**2
    t = ((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)
    if t < 0:
        t = Fraction(0)
    elif t > 1:
        t = Fraction(1)
    qx, qy = ax+t*dx, ay+t*dy
    return (px-qx)**2+(py-qy)**2


def render(segments, radius, width, height):
    """Ink every cell whose centre is within `radius` of some segment.

    The test is exact on rationals and the scan is restricted to each segment's
    own neighbourhood, which is what makes it affordable; the answer is the same
    as scanning the whole grid.
    """
    radius = Fraction(radius)
    squared = radius*radius
    black = set()
    for a, b in segments:
        a = (Fraction(a[0]), Fraction(a[1]))
        b = (Fraction(b[0]), Fraction(b[1]))
        lo_x = int(min(a[0], b[0])-radius-1)
        hi_x = int(max(a[0], b[0])+radius+1)
        lo_y = int(min(a[1], b[1])-radius-1)
        hi_y = int(max(a[1], b[1])+radius+1)
        for i in range(max(0, lo_x), min(width, hi_x+1)):
            for j in range(max(0, lo_y), min(height, hi_y+1)):
                if (i, j) in black:
                    continue
                centre = (Fraction(2*i+1, 2), Fraction(2*j+1, 2))
                if _squared_distance_to_segment(centre, a, b) <= squared:
                    black.add((i, j))
    return Bitmap(width, height, black)


def polyline_segments(polylines):
    """A list of polylines, each a list of points, flattened into segments."""
    segments = []
    for chain in polylines:
        for index in range(len(chain)-1):
            segments.append((tuple(chain[index]), tuple(chain[index+1])))
    return segments


# ---------------------------------------------------------------------------
# Counting: components and holes
# ---------------------------------------------------------------------------

def components(bitmap, *, connectivity=8):
    """The connected black components, largest first. Counting, not geometry."""
    offsets = NEIGHBOURS_8 if connectivity == 8 else NEIGHBOURS_4
    seen, found = set(), []
    for cell in sorted(bitmap.black):
        if cell in seen:
            continue
        piece, queue = set(), deque([cell])
        seen.add(cell)
        while queue:
            i, j = queue.popleft()
            piece.add((i, j))
            for di, dj in offsets:
                other = (i+di, j+dj)
                if other in bitmap.black and other not in seen:
                    seen.add(other)
                    queue.append(other)
        found.append(piece)
    found.sort(key=len, reverse=True)
    return found


def holes(black, width, height):
    """Background 4-components that do not reach the border: the enclosed ones.

    The bitmap is padded by one cell all round first, so a shape touching the
    edge of its own bounding box still has its outside connected to the border.
    """
    outside, queue = set(), deque()
    for i in range(-1, width+1):
        for j in (-1, height):
            if (i, j) not in black:
                outside.add((i, j))
                queue.append((i, j))
    for j in range(-1, height+1):
        for i in (-1, width):
            if (i, j) not in black and (i, j) not in outside:
                outside.add((i, j))
                queue.append((i, j))
    while queue:
        i, j = queue.popleft()
        for di, dj in NEIGHBOURS_4:
            other = (i+di, j+dj)
            if not (-1 <= other[0] <= width and -1 <= other[1] <= height):
                continue
            if other in black or other in outside:
                continue
            outside.add(other)
            queue.append(other)
    count, seen = 0, set()
    for i in range(width):
        for j in range(height):
            cell = (i, j)
            if cell in black or cell in outside or cell in seen:
                continue
            count += 1
            queue = deque([cell])
            seen.add(cell)
            while queue:
                x, y = queue.popleft()
                for di, dj in NEIGHBOURS_4:
                    other = (x+di, y+dj)
                    if other in black or other in outside or other in seen:
                        continue
                    if not (0 <= other[0] < width and 0 <= other[1] < height):
                        continue
                    seen.add(other)
                    queue.append(other)
    return count


# ---------------------------------------------------------------------------
# Thinning: one pixel-wide representative of a thick stroke
# ---------------------------------------------------------------------------

def _zhang_suen_pass(black, step):
    """One half-iteration of Zhang and Suen's thinning, on integers only."""
    #                P9 P2 P3
    #                P8 P1 P4          the ring is read clockwise from north
    #                P7 P6 P5
    ring = ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))
    doomed = set()
    for (i, j) in black:
        values = [1 if (i+di, j+dj) in black else 0 for di, dj in ring]
        filled = sum(values)
        if filled < 2 or filled > 6:
            continue
        transitions = sum(1 for k in range(8)
                          if values[k] == 0 and values[(k+1) % 8] == 1)
        if transitions != 1:
            continue
        p2, p4, p6, p8 = values[0], values[2], values[4], values[6]
        if step == 0:
            if p2*p4*p6 or p4*p6*p8:
                continue
        else:
            if p2*p4*p8 or p2*p6*p8:
                continue
        doomed.add((i, j))
    return doomed


def thin(black):
    """Zhang-Suen thinning: a one-pixel-wide skeleton, deterministic and integral.

    This is the first of the three inexact steps. It chooses a representative of
    a thick stroke; nothing proves that the representative is the centre line,
    and for a stroke of even width it cannot be.
    """
    current = set(black)
    while True:
        removed = False
        for step in (0, 1):
            doomed = _zhang_suen_pass(current, step)
            if doomed:
                current -= doomed
                removed = True
        if not removed:
            return current


# ---------------------------------------------------------------------------
# The skeleton as a graph
# ---------------------------------------------------------------------------

def _degree(cell, skeleton):
    i, j = cell
    return sum(1 for di, dj in NEIGHBOURS_8 if (i+di, j+dj) in skeleton)


RING = ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))


def crossings(cell, skeleton):
    """How many strokes leave this pixel, counted as 0-to-1 steps around its ring.

    The plain neighbour count is useless on a thinned diagonal: a staircase
    pixel has three eight-neighbours and is nonetheless interior to one chain.
    The number of times the ring changes from white to black does not have that
    defect -- it is one at an end, two along a chain, three or more at a real
    branching -- and it is the standard connectivity number.
    """
    values = [1 if (cell[0]+di, cell[1]+dj) in skeleton else 0 for di, dj in RING]
    if not any(values):
        return 0
    return sum(1 for k in range(8) if values[k] == 0 and values[(k+1) % 8] == 1)


def _cluster(cells):
    """8-connected clusters of a set of cells."""
    seen, out = set(), []
    for cell in sorted(cells):
        if cell in seen:
            continue
        piece, queue = set(), deque([cell])
        seen.add(cell)
        while queue:
            i, j = queue.popleft()
            piece.add((i, j))
            for di, dj in NEIGHBOURS_8:
                other = (i+di, j+dj)
                if other in cells and other not in seen:
                    seen.add(other)
                    queue.append(other)
        out.append(piece)
    return out


def _ordered_neighbours(cell):
    """Four-neighbours before diagonals: a chain should not be cut across."""
    i, j = cell
    return [(i+di, j+dj) for di, dj in NEIGHBOURS_4]+[(i+di, j+dj) for di, dj in
                                                     ((1, 1), (-1, 1), (-1, -1), (1, -1))]


def _grow(cluster, skeleton, radius):
    """Every skeleton pixel within Chebyshev `radius` of the cluster, joined to it."""
    grown = set(cluster)
    for _ in range(radius):
        ring = {(i+di, j+dj) for (i, j) in grown
                for di in (-1, 0, 1) for dj in (-1, 0, 1)}
        grown |= ring & skeleton
    return grown


def skeleton_graph(skeleton, *, junction_radius=1):
    """Nodes where the skeleton ends or branches, edges as the pixel chains between.

    A node is a cluster of pixels whose connectivity number is not two -- an end,
    or a branching. Branchings are grown by `junction_radius` first, and that is
    not cosmetic: just outside a three-way junction the three arms are still
    neighbours of one another, so a walk that left along one arm could step
    across into another and report one edge where there are two. Growing the
    junction until the arms have separated is what stops that.

    Everything outside the nodes is interior to an edge, and an edge is found by
    leaving a node and walking the interior until a node is reached again. A
    component with no node at all is a closed loop, and one node is opened on it
    so that the loop becomes an edge from a node to itself.
    """
    skeleton = set(skeleton)
    numbers = {cell: crossings(cell, skeleton) for cell in skeleton}
    special = set()
    for cell, number in numbers.items():
        if number >= 3:
            special |= _grow({cell}, skeleton, junction_radius)
        elif number != 2:
            special.add(cell)
    nodes, node_of = [], {}
    for piece in _cluster(special):
        for cell in piece:
            node_of[cell] = len(nodes)
        nodes.append(piece)
    interior = skeleton-set(node_of)
    used, edges, direct = set(), [], set()
    for index in range(len(nodes)):
        border = {(cell[0]+di, cell[1]+dj) for cell in nodes[index]
                  for di in (-1, 0, 1) for dj in (-1, 0, 1)}
        for cell in sorted(nodes[index]):
            for step in _ordered_neighbours(cell):
                if step in node_of:
                    other = node_of[step]
                    if other != index and (min(index, other), max(index, other)) not in direct:
                        direct.add((min(index, other), max(index, other)))
                        edges.append((index, other, [cell, step]))
                    continue
                if step not in interior or step in used:
                    continue
                chain, current = [], step
                while True:
                    chain.append(current)
                    used.add(current)
                    ahead = [n for n in _ordered_neighbours(current)
                             if n in interior and n not in used
                             and (len(chain) == 1 or n not in border)]
                    if not ahead:
                        break
                    current = ahead[0]
                touching = {node_of[n] for n in _ordered_neighbours(chain[-1]) if n in node_of}
                if not touching:
                    end = index
                elif len(touching) == 1:
                    end = next(iter(touching))
                else:
                    other = sorted(touching-{index})
                    end = other[0] if other else index
                edges.append((index, end, [cell]+chain))
    covered = {cell for _, _, chain in edges for cell in chain} | set(node_of)
    for piece in _cluster(skeleton-covered):
        start = min(piece)
        index = len(nodes)
        nodes.append({start})
        node_of[start] = index
        chain, current = [start], start
        while True:
            ahead = [n for n in _ordered_neighbours(current) if n in piece and n not in chain]
            if not ahead:
                break
            current = ahead[0]
            chain.append(current)
        edges.append((index, index, chain+[start]))
    return nodes, edges


def _deduplicate(nodes, edges):
    """Drop the second copy of an edge that was walked from both of its ends."""
    kept, seen = [], set()
    for a, b, chain in edges:
        key = (min(a, b), max(a, b), frozenset(chain))
        if key in seen:
            continue
        seen.add(key)
        kept.append((a, b, chain))
    return nodes, kept


def centre_of(cluster):
    """The mean cell of a node's pixels, exactly. A float here would decide a branch."""
    total = len(cluster)
    return (Fraction(sum(c[0] for c in cluster), total),
            Fraction(sum(c[1] for c in cluster), total))


def prune(nodes, edges, minimum_length):
    """Remove short branches that end in the air: thinning's spurs, not strokes.

    A spur is an edge one of whose ends has degree one while the other branches.
    Its length is how far the two nodes stand apart, not how many pixels the
    chain has: the chain has already lost a few pixels at each end to the node
    clusters, and measuring it instead would throw away a short but real arm --
    the left half of a bar, say -- along with the spurs. The threshold is given
    by the caller in pixels, taken from the ink's own thickness.
    """
    nodes, edges = _deduplicate(nodes, edges)
    while True:
        degree = {}
        for a, b, _ in edges:
            degree[a] = degree.get(a, 0)+1
            degree[b] = degree.get(b, 0)+1
        victim = None
        for index, (a, b, chain) in enumerate(edges):
            if a == b:
                # a loop this short is a knot thinning left behind, not a stroke
                if len(chain) < minimum_length and degree.get(a, 0) > 2:
                    victim = index
                    break
                continue
            ends = [(a, degree.get(a, 0)), (b, degree.get(b, 0))]
            loose = [n for n, d in ends if d == 1]
            branch = [n for n, d in ends if d >= 3]
            first, second = centre_of(nodes[a]), centre_of(nodes[b])
            apart = (first[0]-second[0])**2+(first[1]-second[1])**2
            # compared as squares, because a square root would be a float and this
            # comparison decides whether a branch of the skeleton survives
            if loose and branch and apart < Fraction(minimum_length)**2 \
                    and len(chain)-1 < minimum_length:
                victim = index
                break
        if victim is None:
            break
        edges.pop(victim)
    used = {n for a, b, _ in edges for n in (a, b)}
    remap = {old: new for new, old in enumerate(sorted(used))}
    nodes = [nodes[old] for old in sorted(used)]
    edges = [(remap[a], remap[b], chain) for a, b, chain in edges]
    return nodes, edges


def dissolve(nodes, edges):
    """Merge the two edges at a node of degree two: it is a corner, not a branching.

    Thinning sometimes leaves a degree-two node where two clusters met. The
    polyline step finds corners on its own, so such a node carries no
    information and joining its two chains loses none.
    """
    while True:
        degree = {}
        for a, b, _ in edges:
            degree[a] = degree.get(a, 0)+1
            degree[b] = degree.get(b, 0)+1
        target = None
        for index in range(len(nodes)):
            if degree.get(index, 0) == 2 and sum(1 for a, b, _ in edges if a == b == index) == 0:
                target = index
                break
        if target is None:
            return nodes, edges
        touching = [e for e in edges if target in (e[0], e[1])]
        if len(touching) != 2:
            return nodes, edges
        (a1, b1, c1), (a2, b2, c2) = touching
        first = list(c1) if b1 == target else list(reversed(c1))
        second = list(c2) if a2 == target else list(reversed(c2))
        far_start = a1 if b1 == target else b1
        far_end = b2 if a2 == target else a2
        # the node's own pixels are not in either chain, and dropping them would
        # leave a gap exactly where the corner is: keep the one nearest its centre
        cluster = nodes[target]
        cx = sum(c[0] for c in cluster)/len(cluster)
        cy = sum(c[1] for c in cluster)/len(cluster)
        middle = min(cluster, key=lambda c: (c[0]-cx)**2+(c[1]-cy)**2)
        bridge = [middle] if middle not in first and middle not in second else []
        merged = first+bridge+(second[1:] if first and second and first[-1] == second[0]
                               else second)
        edges = [e for e in edges if e not in touching]
        edges.append((far_start, far_end, merged))
        used = {n for a, b, _ in edges for n in (a, b)}
        if target in used:
            return nodes, edges
        remap = {old: new for new, old in enumerate(sorted(used))}
        nodes = [nodes[old] for old in sorted(used)]
        edges = [(remap[a], remap[b], chain) for a, b, chain in edges]


# ---------------------------------------------------------------------------
# From a chain of pixels to a polyline
# ---------------------------------------------------------------------------

def _deviation_squared(point, a, b):
    """The squared distance from the point to the line AB, as an exact fraction."""
    ax, ay = a
    bx, by = b
    dx, dy = bx-ax, by-ay
    if dx == 0 and dy == 0:
        return Fraction((point[0]-ax)**2+(point[1]-ay)**2)
    cross = dx*(point[1]-ay)-dy*(point[0]-ax)
    return Fraction(cross*cross, dx*dx+dy*dy)


def simplify_indices(chain, tolerance):
    """The indices Douglas and Peucker keeps: the corners, as positions in the chain."""
    chain = [tuple(p) for p in chain]
    if len(chain) <= 2:
        return list(range(len(chain)))
    bound = Fraction(tolerance)*Fraction(tolerance)
    keep = {0, len(chain)-1}
    stack = [(0, len(chain)-1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo+1:
            continue
        worst, where = Fraction(0), None
        for index in range(lo+1, hi):
            value = _deviation_squared(chain[index], chain[lo], chain[hi])
            if value > worst:
                worst, where = value, index
        if where is not None and worst > bound:
            keep.add(where)
            stack.append((lo, where))
            stack.append((where, hi))
    return sorted(keep)


def straight_pieces(chain, tolerance, margin):
    """Split a chain at its corners and return, for each piece, a pair of pixels on it.

    The pair is not the piece's own ends: a margin is dropped at each end first,
    because thinning rounds a corner and the pixels next to one no longer lie on
    the stroke that leads into it. What comes back is two pixels well inside the
    straight part, which is what the line through the piece should be taken from.
    The corner itself is not guessed here -- it is where two such lines meet, and
    that meeting is a construction, not a measurement.
    """
    chain = [tuple(p) for p in chain]
    cuts = simplify_indices(chain, tolerance)
    pieces = []
    for lo, hi in zip(cuts, cuts[1:]):
        span = hi-lo
        drop = min(margin, max(0, (span-1)//2))
        a, b = lo+drop, hi-drop
        if b <= a:
            a, b = lo, hi
        pieces.append((chain[a], chain[b], (lo, hi)))
    if not pieces and len(chain) >= 2:
        pieces.append((chain[0], chain[-1], (0, len(chain)-1)))
    return pieces


def simplify(chain, tolerance):
    """Douglas and Peucker, with the deviation compared exactly to a rational bound.

    The second of the three inexact steps: the tolerance says how far a chain may
    wander before a corner is declared. The comparison itself is exact; the
    number is a choice.
    """
    chain = [tuple(p) for p in chain]
    if len(chain) <= 2:
        return list(chain)
    bound = Fraction(tolerance)*Fraction(tolerance)
    keep = {0, len(chain)-1}
    stack = [(0, len(chain)-1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo+1:
            continue
        worst, where = Fraction(0), None
        for index in range(lo+1, hi):
            value = _deviation_squared(chain[index], chain[lo], chain[hi])
            if value > worst:
                worst, where = value, index
        if where is not None and worst > bound:
            keep.add(where)
            stack.append((lo, where))
            stack.append((where, hi))
    return [chain[index] for index in sorted(keep)]


# ---------------------------------------------------------------------------
# Two more pens, so that the reader is not only ever shown its own renderer
# ---------------------------------------------------------------------------

def _segments_meet(a, b, c, d):
    """Whether two closed segments share a point, decided exactly on rationals."""
    def side(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])

    def between(p, q, r):
        return min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and \
            min(p[1], q[1]) <= r[1] <= max(p[1], q[1])
    d1, d2 = side(c, d, a), side(c, d, b)
    d3, d4 = side(a, b, c), side(a, b, d)
    if ((d1 > 0) != (d2 > 0) or d1 == 0 or d2 == 0) and \
       ((d3 > 0) != (d4 > 0) or d3 == 0 or d4 == 0):
        if d1 == 0 and not between(c, d, a):
            return False
        if d2 == 0 and not between(c, d, b):
            return False
        if d3 == 0 and not between(a, b, c):
            return False
        if d4 == 0 and not between(a, b, d):
            return False
        return True
    return False


def render_square(segments, radius, width, height):
    """The same strokes drawn with a square pen instead of a round one.

    A cell is black when the segment passes within `radius` of its centre in the
    largest-coordinate sense, which is the same as saying the segment meets the
    square of side 2r about the centre. The corners of the strokes come out
    mitred rather than rounded, the ends are square, and the ink reaches further
    on a diagonal -- so a reader tuned to the round pen is genuinely being shown
    a different drawing of the same letter.
    """
    radius = Fraction(radius)
    black = set()
    for a, b in segments:
        a = (Fraction(a[0]), Fraction(a[1]))
        b = (Fraction(b[0]), Fraction(b[1]))
        lo_x = int(min(a[0], b[0])-radius-1)
        hi_x = int(max(a[0], b[0])+radius+1)
        lo_y = int(min(a[1], b[1])-radius-1)
        hi_y = int(max(a[1], b[1])+radius+1)
        for i in range(max(0, lo_x), min(width, hi_x+1)):
            for j in range(max(0, lo_y), min(height, hi_y+1)):
                if (i, j) in black:
                    continue
                cx, cy = Fraction(2*i+1, 2), Fraction(2*j+1, 2)
                x0, x1 = cx-radius, cx+radius
                y0, y1 = cy-radius, cy+radius
                if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
                    black.add((i, j))
                    continue
                corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                if any(_segments_meet(a, b, corners[k], corners[(k+1) % 4]) for k in range(4)):
                    black.add((i, j))
    return Bitmap(width, height, black)


def speckle(bitmap, *, seed=0, rate=1, only_on_the_edge=True):
    """Flip one cell in `rate` of the ink's boundary, deterministically.

    Real ink has a ragged edge. The choice of which cell to flip is made by a
    hash of the seed and the cell, so the same image comes back every run and
    nothing here depends on a random number generator.
    """
    import hashlib

    if rate <= 0:
        return Bitmap(bitmap.width, bitmap.height, bitmap.black)
    black = set(bitmap.black)
    candidates = set()
    for (i, j) in bitmap.black:
        for di, dj in NEIGHBOURS_8:
            other = (i+di, j+dj)
            if other not in bitmap.black:
                candidates.add((i, j))
                if not only_on_the_edge:
                    continue
                if 0 <= other[0] < bitmap.width and 0 <= other[1] < bitmap.height:
                    candidates.add(other)
    for cell in sorted(candidates):
        digest = hashlib.sha256(f"{seed}:{cell[0]}:{cell[1]}".encode()).digest()
        if digest[0] % rate:
            continue
        if cell in black:
            black.discard(cell)
        else:
            black.add(cell)
    return Bitmap(bitmap.width, bitmap.height, black)


# ---------------------------------------------------------------------------
# Writing a bitmap out
# ---------------------------------------------------------------------------

def write_png(path, bitmap, *, cell=1, background=255, ink=0):
    """The cells as they are, one cell to `cell` pixels. No smoothing anywhere."""
    from PIL import Image

    image = Image.new("L", (bitmap.width*cell, bitmap.height*cell), background)
    pixels = image.load()
    for (i, j) in bitmap.black:
        for a in range(cell):
            for b in range(cell):
                x, y = i*cell+a, (bitmap.height-1-j)*cell+b
                if 0 <= x < image.width and 0 <= y < image.height:
                    pixels[x, y] = ink
    image.save(path)
    return {"path": str(path), "width": image.width, "height": image.height,
            "cells": bitmap.count()}


def paste(pieces, *, columns, gap=4):
    """Lay bitmaps out in a grid, top row first, into one bitmap."""
    if not pieces:
        return Bitmap(1, 1)
    cell_w = max(p.width for p in pieces)+gap
    cell_h = max(p.height for p in pieces)+gap
    rows = (len(pieces)+columns-1)//columns
    sheet = Bitmap(cell_w*columns, cell_h*rows)
    for index, piece in enumerate(pieces):
        column, row = index % columns, rows-1-index//columns
        ox, oy = column*cell_w+gap//2, row*cell_h+gap//2
        for (i, j) in piece.black:
            sheet.black.add((ox+i, oy+j))
    return sheet


def despeckle(black, *, rounds=2):
    """Drop cells with almost no neighbours and fill cells with almost only neighbours.

    The most conservative cleaning there is: a black cell goes only when at most
    one of its eight neighbours is black, and a white cell is filled only when at
    least seven of them are. A stroke two cells wide survives it untouched, which
    a majority filter would not, and a lone speck or a pinhole does not.
    """
    current = set(black)
    for _ in range(rounds):
        neighbours = {}
        for (i, j) in current:
            for di, dj in NEIGHBOURS_8:
                neighbours[(i+di, j+dj)] = neighbours.get((i+di, j+dj), 0)+1
        after = {cell for cell in current if neighbours.get(cell, 0) >= 2}
        after |= {cell for cell, count in neighbours.items()
                  if count >= 7 and cell not in current}
        if after == current:
            break
        current = after
    return current
