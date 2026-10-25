"""Generates the colour-coded swimlane flowcharts in docs/diagrams/ as SVG.

Run from the repo root:  python3 docs/diagrams/src/make_flowcharts.py
PNG versions are made from the SVGs (see docs/diagrams/README.md).
Requirements source: docs/requirements/basic_desc.txt
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent

FONT = "Helvetica, Arial, sans-serif"
COL_W = 150
LABEL_W = 120
TOP = 70
TASK_W, TASK_H = 128, 58
DEC_W, DEC_H = 112, 76
EV_R = 19

LANES = {
    "customer": ("Customer", "#E8F1FB", "#2F6DB5"),
    "system": ("System\n(web app)", "#F1ECF9", "#6B4BA8"),
    "admin": ("Ekte Mat\nadmin /\ncoordinator", "#FFF4E0", "#B86E00"),
    "kitchen": ("Kitchen", "#E9F6EC", "#2E8B57"),
    "delivery": ("Delivery\n(driver)", "#E4F4F5", "#1F7F86"),
}
RED_FILL, RED = "#FDE3E1", "#C0392B"
DEC_FILL, DEC = "#FFF7C2", "#A68A00"
STATUS = {
    "Submitted": "#2F6DB5",
    "Approved": "#2E8B57",
    "In preparation": "#D97706",
    "Delivered": "#1B5E20",
    "Rejected": RED,
    "Cancelled": RED,
}


class Chart:
    def __init__(self, title, subtitle, lanes, lane_h=170):
        self.title, self.subtitle = title, subtitle
        self.lanes, self.lane_h = lanes, lane_h
        self.nodes, self.edges = {}, []
        self.ncols = 0

    # kind: start | end | endbad | task | bad | dec | timer | msg
    def node(self, id, lane, col, kind, label="", row=0, status=None, h=None, above=False):
        self.ncols = max(self.ncols, col + 1)
        self.nodes[id] = dict(lane=lane, col=col, kind=kind, label=label, row=row,
                              status=status, h=h or TASK_H, above=above)

    def edge(self, a, b, label="", src=None, dst=None, via=(), lpos=None, mx=None):
        self.edges.append(dict(a=a, b=b, label=label, src=src, dst=dst, via=via, lpos=lpos, mx=mx))

    # geometry ---------------------------------------------------------
    def center(self, n):
        x = LABEL_W + n["col"] * COL_W + COL_W / 2
        li = self.lanes.index(n["lane"])
        y = TOP + li * self.lane_h + self.lane_h / 2 + n["row"] * 42
        return x, y

    def half(self, n):
        k = n["kind"]
        if k in ("task", "bad"):
            return TASK_W / 2, n["h"] / 2
        if k == "dec":
            return DEC_W / 2, DEC_H / 2
        return EV_R, EV_R

    def port(self, id, side):
        n = self.nodes[id]
        x, y = self.center(n)
        hw, hh = self.half(n)
        return {"r": (x + hw, y), "l": (x - hw, y), "t": (x, y - hh), "b": (x, y + hh)}[side]

    def route(self, e):
        A, B = self.nodes[e["a"]], self.nodes[e["b"]]
        ax, ay = self.center(A)
        bx, by = self.center(B)
        src = e["src"] or ("r" if bx > ax else ("b" if by > ay else "t"))
        if e["dst"]:
            dst = e["dst"]
        elif abs(ay - by) < 1 or src == "r":
            dst = "l"
        else:
            dst = "t" if by > ay else "b"
        p0, p1 = self.port(e["a"], src), self.port(e["b"], dst)
        pts = [p0]
        for v in e["via"]:
            # via entries: ("x", value) / ("y", value) move along one axis
            last = pts[-1]
            pts.append((v[1], last[1]) if v[0] == "x" else (last[0], v[1]))
        last = pts[-1]
        if dst == "l":
            if abs(last[1] - p1[1]) > 0.5:
                if src in ("t", "b") and not e["via"]:
                    pts.append((last[0], p1[1]))
                else:
                    mx = e["mx"] if e["mx"] is not None else (
                        p1[0] - 22 if e["via"] else (last[0] + p1[0]) / 2)
                    pts += [(mx, last[1]), (mx, p1[1])]
        else:  # entering top/bottom
            if abs(last[0] - p1[0]) > 0.5:
                pts.append((p1[0], last[1]))
        pts.append(p1)
        return pts

    # drawing ----------------------------------------------------------
    def text(self, x, y, s, size=12, weight="normal", fill="#1F2328", anchor="middle"):
        lines = s.split("\n")
        lh = size * 1.18
        y0 = y - (len(lines) - 1) * lh / 2 + size * 0.36
        out = [f'<text x="{x:.1f}" y="{y0:.1f}" font-family="{FONT}" font-size="{size}" '
               f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">']
        for i, ln in enumerate(lines):
            out.append(f'<tspan x="{x:.1f}" dy="{0 if i == 0 else lh:.1f}">{escape(ln)}</tspan>')
        out.append("</text>")
        return "".join(out)

    def draw_node(self, n):
        x, y = self.center(n)
        k, lab = n["kind"], n["label"]
        _, _, accent = LANES[n["lane"]]
        s = []
        if k in ("task", "bad"):
            fill, stroke = (RED_FILL, RED) if k == "bad" else ("#FFFFFF", accent)
            h = n["h"]
            s.append(f'<rect x="{x - TASK_W / 2}" y="{y - h / 2}" width="{TASK_W}" height="{h}" rx="9" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            s.append(self.text(x, y, lab, 11.5))
        elif k == "dec":
            s.append(f'<polygon points="{x},{y - DEC_H / 2} {x + DEC_W / 2},{y} {x},{y + DEC_H / 2} '
                     f'{x - DEC_W / 2},{y}" fill="{DEC_FILL}" stroke="{DEC}" stroke-width="2"/>')
            s.append(self.text(x, y, lab, 10.5))
        else:
            if k == "start":
                s.append(f'<circle cx="{x}" cy="{y}" r="{EV_R}" fill="#E7F6E9" stroke="#2E7D32" stroke-width="2.5"/>')
            elif k in ("end", "endbad"):
                c = RED if k == "endbad" else "#1F2328"
                f = RED_FILL if k == "endbad" else "#EDEDED"
                s.append(f'<circle cx="{x}" cy="{y}" r="{EV_R}" fill="{f}" stroke="{c}" stroke-width="5"/>')
            elif k == "timer":
                s.append(f'<circle cx="{x}" cy="{y}" r="{EV_R}" fill="#FFFFFF" stroke="#6B4BA8" stroke-width="2"/>')
                s.append(f'<circle cx="{x}" cy="{y}" r="{EV_R - 4}" fill="#F1ECF9" stroke="#6B4BA8" stroke-width="1.5"/>')
                s.append(f'<path d="M{x},{y - 9} L{x},{y} L{x + 7},{y + 4}" fill="none" stroke="#6B4BA8" stroke-width="2"/>')
            elif k == "msg":
                s.append(f'<circle cx="{x}" cy="{y}" r="{EV_R}" fill="#E7F6E9" stroke="#2E7D32" stroke-width="2.5"/>')
                s.append(f'<rect x="{x - 10}" y="{y - 7}" width="20" height="14" fill="#FFFFFF" stroke="#2E7D32" stroke-width="1.5"/>')
                s.append(f'<path d="M{x - 10},{y - 7} L{x},{y + 1} L{x + 10},{y - 7}" fill="none" stroke="#2E7D32" stroke-width="1.5"/>')
            if lab:
                off = EV_R + 14 + 6.2 * lab.count("\n")
                s.append(self.text(x, y - off if n.get("above") else y + off, lab, 10.5, fill="#3D444D"))
        if n["status"]:
            st = n["status"]
            c = STATUS[st]
            w = 12 + 6.4 * len(st) + 14
            _, hh = self.half(n)
            by = y - hh - 13
            s.append(f'<rect x="{x - w / 2}" y="{by - 9}" width="{w}" height="18" rx="9" fill="{c}"/>')
            s.append(self.text(x, by, "→ " + st, 10, "bold", "#FFFFFF"))
        return "".join(s)

    def draw_edge(self, e):
        pts = self.route(e)
        d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        bad = self.nodes[e["b"]]["kind"] in ("bad", "endbad")
        col = RED if bad else "#57606A"
        dash = ' stroke-dasharray="6 4"' if e["label"].startswith("loop") else ""
        path = (f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.6"{dash} '
                f'marker-end="url(#{"arrbad" if bad else "arr"})"/>')
        s = []
        if e["label"]:
            lab = e["label"].removeprefix("loop:").strip()
            if e["lpos"]:
                lx, ly = e["lpos"]
            else:
                (x0, y0), (x1, y1) = pts[0], pts[1]
                if abs(y0 - y1) < 1:
                    lx, ly = x0 + 16, y0 - 9
                else:
                    lx, ly = x0 + 8, (y0 + y1) / 2
            anchor = "start"
            w = 6.2 * max(len(l) for l in lab.split("\n")) + 8
            nl = lab.count("\n") + 1
            s.append(f'<rect x="{lx - 3}" y="{ly - 8 * nl}" width="{w}" height="{16 * nl}" rx="3" fill="#FFFFFF" opacity="0.9"/>')
            s.append(self.text(lx + 1, ly, lab, 10.5, "bold", col, anchor))
        return path, "".join(s)

    def svg(self, legend_extra=()):
        width = LABEL_W + self.ncols * COL_W + 30
        lanes_h = len(self.lanes) * self.lane_h
        legend_y = TOP + lanes_h + 30
        height = legend_y + 170
        s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}">',
             '<defs>'
             '<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
             '<path d="M0,0 L10,5 L0,10 z" fill="#57606A"/></marker>'
             f'<marker id="arrbad" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
             f'<path d="M0,0 L10,5 L0,10 z" fill="{RED}"/></marker></defs>',
             f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
             self.text(24, 26, self.title, 20, "bold", anchor="start"),
             self.text(24, 50, self.subtitle, 12, fill="#57606A", anchor="start")]
        for i, key in enumerate(self.lanes):
            name, tint, accent = LANES[key]
            y = TOP + i * self.lane_h
            s.append(f'<rect x="0" y="{y}" width="{width}" height="{self.lane_h}" fill="{tint}" '
                     f'stroke="#FFFFFF" stroke-width="3"/>')
            s.append(f'<rect x="0" y="{y}" width="{LABEL_W - 14}" height="{self.lane_h}" fill="{accent}" '
                     f'stroke="#FFFFFF" stroke-width="3"/>')
            s.append(self.text((LABEL_W - 14) / 2, y + self.lane_h / 2, name, 13, "bold", "#FFFFFF"))
        drawn = [self.draw_edge(e) for e in self.edges]
        s += [p for p, _ in drawn]
        s += [self.draw_node(n) for n in self.nodes.values()]
        s += [l for _, l in drawn]
        s.append(self.legend(24, legend_y, legend_extra))
        s.append("</svg>")
        return "\n".join(s)

    def legend(self, x, y, extra):
        s = [self.text(x, y, "Legend", 13, "bold", anchor="start")]
        y += 34
        items = [
            ("start", "Start"), ("msg", "Message received"), ("timer", "Timer (automatic)"),
            ("end", "End"), ("endbad", "End: rejected / cancelled"),
        ]
        cx = x + 12
        for kind, lab in items:
            n = dict(lane="system", col=0, kind=kind, label="", row=0, status=None, h=TASK_H)
            g = self.draw_node(n)
            ox, oy = self.center(n)
            s.append(f'<g transform="translate({cx - ox},{y - oy}) scale(1)">{g}</g>')
            s.append(self.text(cx + 26, y, lab, 11.5, anchor="start"))
            cx += 52 + 6.3 * len(lab)
        y += 40
        cx = x
        s.append(f'<rect x="{cx}" y="{y - 13}" width="44" height="26" rx="6" fill="#FFFFFF" stroke="#57606A" stroke-width="2"/>')
        s.append(self.text(cx + 52, y, "Task (border = lane colour)", 11.5, anchor="start"))
        cx += 240
        s.append(f'<rect x="{cx}" y="{y - 13}" width="44" height="26" rx="6" fill="{RED_FILL}" stroke="{RED}" stroke-width="2"/>')
        s.append(self.text(cx + 52, y, "Reject / refuse / cancel path", 11.5, anchor="start"))
        cx += 250
        s.append(f'<polygon points="{cx + 22},{y - 15} {cx + 44},{y} {cx + 22},{y + 15} {cx},{y}" fill="{DEC_FILL}" stroke="{DEC}" stroke-width="2"/>')
        s.append(self.text(cx + 52, y, "Decision", 11.5, anchor="start"))
        cx += 130
        s.append(self.text(cx, y, "Order status:", 11.5, "bold", anchor="start"))
        cx += 88
        for st, c in STATUS.items():
            w = 12 + 6.4 * len(st)
            s.append(f'<rect x="{cx}" y="{y - 9}" width="{w}" height="18" rx="9" fill="{c}"/>')
            s.append(self.text(cx + w / 2, y, st, 10, "bold", "#FFFFFF"))
            cx += w + 8
        y += 36
        for line in extra:
            s.append(self.text(x, y, line, 11.5, fill="#3D444D", anchor="start"))
            y += 18
        return "".join(s)


MINIMUMS = ("Event-type minimum guests (example values; admin can set 1–265): "
            "corporate lunch 8 · birthday 10 · confirmation 15 · christmas party 20 · "
            "conference 30 · wedding 50. The minimum in force when the order is placed is saved on the order.")


def customer_journey():
    c = Chart("1 \u00b7 Customer journey: from first visit to delivered order, with a change in the order",
              "Ekte Mat ordering system (to-be). Source: docs/requirements/basic_desc.txt. "
              "Payment is not integrated: the customer picks a payment option on the order.",
              ["customer", "system", "admin"], lane_h=190)
    c.node("start", "customer", 0, "start", "Needs\ncatering")
    c.node("browse", "customer", 1, "task", "Browse menus\ngrouped by\nevent type")
    c.node("cart", "customer", 2, "task", "Add dishes to cart,\nset quantities\n(total shown)")
    c.node("minok", "system", 3, "dec", "Quantity \u2265\nevent-type\nminimum?")
    c.node("below", "customer", 3, "bad", "Shown: below\nminimum \u2013\nadjust cart", row=1.1)
    c.node("login", "customer", 4, "task", "Log in or register\n(unique e-mail)")
    c.node("details", "customer", 5, "task", "Fill in: event date,\nguests, address,\nallergies & diets,\ndelivery notes,\npayment option", h=86)
    c.node("submit", "customer", 6, "task", "Submit order")
    c.node("store", "system", 7, "task", "Save order +\nminimum in force;\ne-mail receipt", status="Submitted")
    c.node("review", "admin", 8, "task", "Review order:\ncapacity, dishes,\nallergies")
    c.node("approve", "admin", 9, "dec", "Approve?")
    c.node("ok", "admin", 10, "task", "Approve order", row=-0.8, status="Approved")
    c.node("reject", "admin", 10, "bad", "Reject with\nreason; customer\nis e-mailed", row=1.25, status="Rejected")
    c.node("rejend", "admin", 11, "endbad", "", row=1.25)
    c.node("notify", "system", 11, "task", "E-mail customer:\norder approved")
    c.node("t7", "system", 12, "timer", "7 days before:\nreminder to change\nor cancel before\nthe 5-day limit")
    c.node("change", "customer", 13, "task", "Changes guest\ncount in the order", row=-0.6)
    c.node("in_time", "system", 14, "dec", "More than\n5 days before\nevent?")
    c.node("refuse", "customer", 15, "bad", "Shown: change\nrefused \u2013 order\nis locked", row=1.1)
    c.node("ask", "customer", 16, "task", "Sends a question\nabout the order", row=1.1)
    c.node("newmin", "system", 15, "dec", "New quantity \u2265\nsaved\nminimum?")
    c.node("update", "system", 16, "task", "Update order;\nnotify Ekte Mat")
    c.node("t5", "system", 17, "timer", "5 days before:\nlock order")
    c.node("answer", "admin", 18, "task", "Reads and\nanswers question", row=1.25)
    c.node("prep", "admin", 19, "task", "Prepare and\ndeliver (see\ndiagram 2)", row=-0.6, status="In preparation")
    c.node("receive", "customer", 20, "task", "Receives the\ncatering")
    c.node("history", "system", 21, "task", "Order moved to\nhistory (read-only)", status="Delivered")
    c.node("end", "system", 22, "end", "Done")

    c.edge("start", "browse"); c.edge("browse", "cart"); c.edge("cart", "minok")
    c.edge("minok", "below", "no", src="t", dst="b")
    c.edge("below", "cart", "loop: adjust", src="l", dst="b",
           lpos=(c.center(c.nodes["cart"])[0] + 12, c.center(c.nodes["below"])[1] + 14))
    c.edge("minok", "login", "yes", src="r")
    c.edge("login", "details"); c.edge("details", "submit"); c.edge("submit", "store")
    c.edge("store", "review"); c.edge("review", "approve")
    c.edge("approve", "reject", "no", src="b", dst="l")
    c.edge("reject", "rejend")
    c.edge("approve", "ok", "yes", src="t", dst="l")
    c.edge("ok", "notify"); c.edge("notify", "t7")
    c.edge("t7", "change"); c.edge("change", "in_time")
    c.edge("in_time", "refuse", "no", src="t", dst="l")
    c.edge("in_time", "newmin", "yes", src="r")
    loop_y = TOP + 2 * 190 - 16
    c.edge("newmin", "change", "loop: no \u2013 adjust", src="b", dst="b", via=[("y", loop_y)],
           lpos=(c.center(c.nodes["in_time"])[0] - 20, loop_y - 10))
    c.edge("newmin", "update", "yes")
    c.edge("update", "t5")
    c.edge("refuse", "ask")
    c.edge("ask", "answer", src="r", dst="t")
    prep_left = c.port("prep", "l")[0]
    c.edge("t5", "prep", src="r", dst="l", mx=prep_left - 11)
    c.edge("answer", "prep", src="r", dst="l", mx=prep_left - 11)
    c.edge("prep", "receive", src="r", dst="b")
    c.edge("receive", "history", src="r", dst="l")
    c.edge("history", "end")
    return c.svg([MINIMUMS])


def admin_flow():
    c = Chart("2 \u00b7 Admin side: one order moving between the lanes, from submitted to paid",
              "Ekte Mat ordering system (to-be). Source: docs/requirements/basic_desc.txt. "
              "Status badges show where the order status changes.",
              ["customer", "system", "admin", "kitchen", "delivery"], lane_h=180)
    c.node("start", "customer", 0, "msg", "Order\nsubmitted")
    c.node("store", "system", 1, "task", "Save order;\nadd to admin\norder list", status="Submitted")
    c.node("open", "admin", 2, "task", "Open order page\n(list filtered by\nstatus, event date)")
    c.node("check", "admin", 3, "task", "Check capacity,\ndishes, allergies\nper guest group")
    c.node("approve", "admin", 4, "dec", "Approve?")
    c.node("ok", "admin", 5, "task", "Approve; set\npayment status\nfrom chosen option", row=-0.8, status="Approved")
    c.node("reject", "admin", 5, "bad", "Reject with\nreason", row=1.25, status="Rejected")
    c.node("rejend", "admin", 6, "endbad", "", row=1.25)
    c.node("notify", "system", 6, "task", "E-mail customer:\napproved")
    c.node("t7", "system", 7, "timer", "7 days before:\nreminder")
    c.node("resp", "system", 8, "dec", "Customer action\nbefore 5-day\nlimit?")
    c.node("cancel", "customer", 9, "bad", "Cancels the\norder", status="Cancelled")
    c.node("cancend", "customer", 10, "endbad", "")
    c.node("chg", "admin", 9, "task", "Review changed\norder (guests \u2265\nsaved minimum)")
    c.node("t5", "system", 10, "timer", "5 days before:\nlock order", above=True)
    c.node("release", "admin", 11, "task", "Release order\nto kitchen", status="In preparation")
    c.node("screen", "kitchen", 12, "task", "Kitchen screen:\nportions per dish,\nallergies in red")
    c.node("confirm", "kitchen", 13, "task", "Confirm allergies\nare seen")
    c.node("cook", "kitchen", 14, "task", "Prepare and\npack the order")
    c.node("drive", "delivery", 15, "task", "Deliver to address\n(follow delivery\nnotes)")
    c.node("done", "delivery", 16, "task", "Confirm\ndelivered")
    c.node("hist", "system", 17, "task", "Mark delivered;\norder becomes\nread-only", status="Delivered")
    c.node("pay", "admin", 18, "task", "Update payment\nstatus (invoiced /\npaid)")
    c.node("end", "admin", 19, "end", "Order\nclosed")

    c.edge("start", "store", src="r", dst="l"); c.edge("store", "open", src="r", dst="t")
    c.edge("open", "check"); c.edge("check", "approve")
    c.edge("approve", "reject", "no", src="b", dst="l")
    c.edge("reject", "rejend")
    c.edge("approve", "ok", "yes", src="t", dst="l")
    c.edge("ok", "notify", src="r", dst="b"); c.edge("notify", "t7")
    c.edge("t7", "resp")
    c.edge("resp", "cancel", "cancels", src="t", dst="l")
    c.edge("cancel", "cancend")
    c.edge("resp", "chg", "changes", src="b", dst="t")
    c.edge("resp", "t5", "no action", src="r", dst="l")
    c.edge("chg", "t5", src="r", dst="b")
    c.edge("t5", "release", src="r", dst="l")
    c.edge("release", "screen", src="r", dst="t"); c.edge("screen", "confirm"); c.edge("confirm", "cook")
    c.edge("cook", "drive", src="r", dst="t"); c.edge("drive", "done")
    c.edge("done", "hist", src="r", dst="b"); c.edge("hist", "pay", src="r", dst="t")
    c.edge("pay", "end")
    return c.svg([
        "Questions: at any time the customer can send a question about an order; the admin reads and answers it on the order page (diagram 1).",
        "Lanes follow the case interviews: coordinator (Sunniva), kitchen (Mateo) and driver. " + MINIMUMS.split(". The")[0] + ".",
    ])


if __name__ == "__main__":
    (OUT / "flow_1_customer_journey.svg").write_text(customer_journey(), encoding="utf-8")
    (OUT / "flow_2_admin_order_lanes.svg").write_text(admin_flow(), encoding="utf-8")
    print("wrote", OUT / "flow_1_customer_journey.svg", OUT / "flow_2_admin_order_lanes.svg")
