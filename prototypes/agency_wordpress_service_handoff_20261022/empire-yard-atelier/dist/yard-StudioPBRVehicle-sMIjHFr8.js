import { b as X, j as re } from "./yard-main-BvZkRFEe.js";
import { R as Yt, V as J, S as rt, Q as pe, O as fe, a as S, P as me, M as z, T as $, b as Zt, c as Wt, L as pt, d as Ae, F as Ee, e as K, C as V, f as Vt, g as qt, D as zt, h as Me, I as $t, i as es, j as Et, k as ts, l as ss, B as ce, m as ns, n as Mt, N as os, o as rs, p as is, q as Ft, r as as, s as Ke, t as As, u as cs, v as Bs, w as Le, x as ls, y as Gt, z as us, A as ae, E as hs, G as Dt, H as Cs, J as ds, K as it, U as fs, W as ms, X as ps, Y as Es, Z as Je, _ as Ms, $ as Fs, a0 as Gs, a1 as Ds, a2 as gs, a3 as gt, a4 as Is, a5 as at, a6 as At, a7 as ct, a8 as Bt, a9 as Rs, aa as Ts, ab as It, ac as bs, ad as Hs, ae as Ls, af as we, ag as k, ah as Js, ai as ys } from "./yard-ShowroomScene-B_cDuCQf.js";
const Os = parseInt(Yt.replace(/\D+/g, ""));
var Ps = Object.defineProperty, Ss = (h, t, s) => t in h ? Ps(h, t, { enumerable: !0, configurable: !0, writable: !0, value: s }) : h[t] = s, xs = (h, t, s) => (Ss(h, t + "", s), s);
class Ks {
  constructor() {
    xs(this, "_listeners");
  }
  /**
   * Adds a listener to an event type.
   * @param type The type of event to listen to.
   * @param listener The function that gets called when the event is fired.
   */
  addEventListener(t, s) {
    this._listeners === void 0 && (this._listeners = {});
    const e = this._listeners;
    e[t] === void 0 && (e[t] = []), e[t].indexOf(s) === -1 && e[t].push(s);
  }
  /**
      * Checks if listener is added to an event type.
      * @param type The type of event to listen to.
      * @param listener The function that gets called when the event is fired.
      */
  hasEventListener(t, s) {
    if (this._listeners === void 0)
      return !1;
    const e = this._listeners;
    return e[t] !== void 0 && e[t].indexOf(s) !== -1;
  }
  /**
      * Removes a listener from an event type.
      * @param type The type of the listener that gets removed.
      * @param listener The listener function that gets removed.
      */
  removeEventListener(t, s) {
    if (this._listeners === void 0)
      return;
    const n = this._listeners[t];
    if (n !== void 0) {
      const o = n.indexOf(s);
      o !== -1 && n.splice(o, 1);
    }
  }
  /**
      * Fire an event type.
      * @param event The event that gets fired.
      */
  dispatchEvent(t) {
    if (this._listeners === void 0)
      return;
    const e = this._listeners[t.type];
    if (e !== void 0) {
      t.target = this;
      const n = e.slice(0);
      for (let o = 0, r = n.length; o < r; o++)
        n[o].call(this, t);
      t.target = null;
    }
  }
}
var Us = Object.defineProperty, Ns = (h, t, s) => t in h ? Us(h, t, { enumerable: !0, configurable: !0, writable: !0, value: s }) : h[t] = s, F = (h, t, s) => (Ns(h, typeof t != "symbol" ? t + "" : t, s), s);
const he = /* @__PURE__ */ new Zt(), lt = /* @__PURE__ */ new Wt(), ws = Math.cos(70 * (Math.PI / 180)), ut = (h, t) => (h % t + t) % t;
let vs = class extends Ks {
  constructor(t, s) {
    super(), F(this, "object"), F(this, "domElement"), F(this, "enabled", !0), F(this, "target", new J()), F(this, "minDistance", 0), F(this, "maxDistance", 1 / 0), F(this, "minZoom", 0), F(this, "maxZoom", 1 / 0), F(this, "minPolarAngle", 0), F(this, "maxPolarAngle", Math.PI), F(this, "minAzimuthAngle", -1 / 0), F(this, "maxAzimuthAngle", 1 / 0), F(this, "enableDamping", !1), F(this, "dampingFactor", 0.05), F(this, "enableZoom", !0), F(this, "zoomSpeed", 1), F(this, "enableRotate", !0), F(this, "rotateSpeed", 1), F(this, "enablePan", !0), F(this, "panSpeed", 1), F(this, "screenSpacePanning", !0), F(this, "keyPanSpeed", 7), F(this, "zoomToCursor", !1), F(this, "autoRotate", !1), F(this, "autoRotateSpeed", 2), F(this, "reverseOrbit", !1), F(this, "reverseHorizontalOrbit", !1), F(this, "reverseVerticalOrbit", !1), F(this, "keys", { LEFT: "ArrowLeft", UP: "ArrowUp", RIGHT: "ArrowRight", BOTTOM: "ArrowDown" }), F(this, "mouseButtons", {
      LEFT: z.ROTATE,
      MIDDLE: z.DOLLY,
      RIGHT: z.PAN
    }), F(this, "touches", { ONE: $.ROTATE, TWO: $.DOLLY_PAN }), F(this, "target0"), F(this, "position0"), F(this, "zoom0"), F(this, "_domElementKeyEvents", null), F(this, "getPolarAngle"), F(this, "getAzimuthalAngle"), F(this, "setPolarAngle"), F(this, "setAzimuthalAngle"), F(this, "getDistance"), F(this, "getZoomScale"), F(this, "listenToKeyEvents"), F(this, "stopListenToKeyEvents"), F(this, "saveState"), F(this, "reset"), F(this, "update"), F(this, "connect"), F(this, "dispose"), F(this, "dollyIn"), F(this, "dollyOut"), F(this, "getScale"), F(this, "setScale"), this.object = t, this.domElement = s, this.target0 = this.target.clone(), this.position0 = this.object.position.clone(), this.zoom0 = this.object.zoom, this.getPolarAngle = () => B.phi, this.getAzimuthalAngle = () => B.theta, this.setPolarAngle = (l) => {
      let f = ut(l, 2 * Math.PI), I = B.phi;
      I < 0 && (I += 2 * Math.PI), f < 0 && (f += 2 * Math.PI);
      let H = Math.abs(f - I);
      2 * Math.PI - H < H && (f < I ? f += 2 * Math.PI : I += 2 * Math.PI), c.phi = f - I, e.update();
    }, this.setAzimuthalAngle = (l) => {
      let f = ut(l, 2 * Math.PI), I = B.theta;
      I < 0 && (I += 2 * Math.PI), f < 0 && (f += 2 * Math.PI);
      let H = Math.abs(f - I);
      2 * Math.PI - H < H && (f < I ? f += 2 * Math.PI : I += 2 * Math.PI), c.theta = f - I, e.update();
    }, this.getDistance = () => e.object.position.distanceTo(e.target), this.listenToKeyEvents = (l) => {
      l.addEventListener("keydown", be), this._domElementKeyEvents = l;
    }, this.stopListenToKeyEvents = () => {
      this._domElementKeyEvents.removeEventListener("keydown", be), this._domElementKeyEvents = null;
    }, this.saveState = () => {
      e.target0.copy(e.target), e.position0.copy(e.object.position), e.zoom0 = e.object.zoom;
    }, this.reset = () => {
      e.target.copy(e.target0), e.object.position.copy(e.position0), e.object.zoom = e.zoom0, e.object.updateProjectionMatrix(), e.dispatchEvent(n), e.update(), i = a.NONE;
    }, this.update = (() => {
      const l = new J(), f = new J(0, 1, 0), I = new pe().setFromUnitVectors(t.up, f), H = I.clone().invert(), y = new J(), U = new pe(), Q = 2 * Math.PI;
      return function() {
        const ot = e.object.position;
        I.setFromUnitVectors(t.up, f), H.copy(I).invert(), l.copy(ot).sub(e.target), l.applyQuaternion(I), B.setFromVector3(l), e.autoRotate && i === a.NONE && De(Lt()), e.enableDamping ? (B.theta += c.theta * e.dampingFactor, B.phi += c.phi * e.dampingFactor) : (B.theta += c.theta, B.phi += c.phi);
        let N = e.minAzimuthAngle, w = e.maxAzimuthAngle;
        isFinite(N) && isFinite(w) && (N < -Math.PI ? N += Q : N > Math.PI && (N -= Q), w < -Math.PI ? w += Q : w > Math.PI && (w -= Q), N <= w ? B.theta = Math.max(N, Math.min(w, B.theta)) : B.theta = B.theta > (N + w) / 2 ? Math.max(N, B.theta) : Math.min(w, B.theta)), B.phi = Math.max(e.minPolarAngle, Math.min(e.maxPolarAngle, B.phi)), B.makeSafe(), e.enableDamping === !0 ? e.target.addScaledVector(C, e.dampingFactor) : e.target.add(C), e.zoomToCursor && L || e.object.isOrthographicCamera ? B.radius = Re(B.radius) : B.radius = Re(B.radius * u), l.setFromSpherical(B), l.applyQuaternion(H), ot.copy(e.target).add(l), e.object.matrixAutoUpdate || e.object.updateMatrix(), e.object.lookAt(e.target), e.enableDamping === !0 ? (c.theta *= 1 - e.dampingFactor, c.phi *= 1 - e.dampingFactor, C.multiplyScalar(1 - e.dampingFactor)) : (c.set(0, 0, 0), C.set(0, 0, 0));
        let se = !1;
        if (e.zoomToCursor && L) {
          let ne = null;
          if (e.object instanceof me && e.object.isPerspectiveCamera) {
            const oe = l.length();
            ne = Re(oe * u);
            const ue = oe - ne;
            e.object.position.addScaledVector(O, ue), e.object.updateMatrixWorld();
          } else if (e.object.isOrthographicCamera) {
            const oe = new J(P.x, P.y, 0);
            oe.unproject(e.object), e.object.zoom = Math.max(e.minZoom, Math.min(e.maxZoom, e.object.zoom / u)), e.object.updateProjectionMatrix(), se = !0;
            const ue = new J(P.x, P.y, 0);
            ue.unproject(e.object), e.object.position.sub(ue).add(oe), e.object.updateMatrixWorld(), ne = l.length();
          } else
            console.warn("WARNING: OrbitControls.js encountered an unknown camera type - zoom to cursor disabled."), e.zoomToCursor = !1;
          ne !== null && (e.screenSpacePanning ? e.target.set(0, 0, -1).transformDirection(e.object.matrix).multiplyScalar(ne).add(e.object.position) : (he.origin.copy(e.object.position), he.direction.set(0, 0, -1).transformDirection(e.object.matrix), Math.abs(e.object.up.dot(he.direction)) < ws ? t.lookAt(e.target) : (lt.setFromNormalAndCoplanarPoint(e.object.up, e.target), he.intersectPlane(lt, e.target))));
        } else e.object instanceof fe && e.object.isOrthographicCamera && (se = u !== 1, se && (e.object.zoom = Math.max(e.minZoom, Math.min(e.maxZoom, e.object.zoom / u)), e.object.updateProjectionMatrix()));
        return u = 1, L = !1, se || y.distanceToSquared(e.object.position) > A || 8 * (1 - U.dot(e.object.quaternion)) > A ? (e.dispatchEvent(n), y.copy(e.object.position), U.copy(e.object.quaternion), se = !1, !0) : !1;
      };
    })(), this.connect = (l) => {
      e.domElement = l, e.domElement.style.touchAction = "none", e.domElement.addEventListener("contextmenu", st), e.domElement.addEventListener("pointerdown", et), e.domElement.addEventListener("pointercancel", te), e.domElement.addEventListener("wheel", tt);
    }, this.dispose = () => {
      var l, f, I, H, y, U;
      e.domElement && (e.domElement.style.touchAction = "auto"), (l = e.domElement) == null || l.removeEventListener("contextmenu", st), (f = e.domElement) == null || f.removeEventListener("pointerdown", et), (I = e.domElement) == null || I.removeEventListener("pointercancel", te), (H = e.domElement) == null || H.removeEventListener("wheel", tt), (y = e.domElement) == null || y.ownerDocument.removeEventListener("pointermove", Te), (U = e.domElement) == null || U.ownerDocument.removeEventListener("pointerup", te), e._domElementKeyEvents !== null && e._domElementKeyEvents.removeEventListener("keydown", be);
    };
    const e = this, n = { type: "change" }, o = { type: "start" }, r = { type: "end" }, a = {
      NONE: -1,
      ROTATE: 0,
      DOLLY: 1,
      PAN: 2,
      TOUCH_ROTATE: 3,
      TOUCH_PAN: 4,
      TOUCH_DOLLY_PAN: 5,
      TOUCH_DOLLY_ROTATE: 6
    };
    let i = a.NONE;
    const A = 1e-6, B = new rt(), c = new rt();
    let u = 1;
    const C = new J(), d = new S(), p = new S(), m = new S(), E = new S(), G = new S(), D = new S(), g = new S(), R = new S(), M = new S(), O = new J(), P = new S();
    let L = !1;
    const b = [], Be = {};
    function Lt() {
      return 2 * Math.PI / 60 / 60 * e.autoRotateSpeed;
    }
    function Y() {
      return Math.pow(0.95, e.zoomSpeed);
    }
    function De(l) {
      e.reverseOrbit || e.reverseHorizontalOrbit ? c.theta += l : c.theta -= l;
    }
    function _e(l) {
      e.reverseOrbit || e.reverseVerticalOrbit ? c.phi += l : c.phi -= l;
    }
    const Qe = (() => {
      const l = new J();
      return function(I, H) {
        l.setFromMatrixColumn(H, 0), l.multiplyScalar(-I), C.add(l);
      };
    })(), ke = (() => {
      const l = new J();
      return function(I, H) {
        e.screenSpacePanning === !0 ? l.setFromMatrixColumn(H, 1) : (l.setFromMatrixColumn(H, 0), l.crossVectors(e.object.up, l)), l.multiplyScalar(I), C.add(l);
      };
    })(), q = (() => {
      const l = new J();
      return function(I, H) {
        const y = e.domElement;
        if (y && e.object instanceof me && e.object.isPerspectiveCamera) {
          const U = e.object.position;
          l.copy(U).sub(e.target);
          let Q = l.length();
          Q *= Math.tan(e.object.fov / 2 * Math.PI / 180), Qe(2 * I * Q / y.clientHeight, e.object.matrix), ke(2 * H * Q / y.clientHeight, e.object.matrix);
        } else y && e.object instanceof fe && e.object.isOrthographicCamera ? (Qe(
          I * (e.object.right - e.object.left) / e.object.zoom / y.clientWidth,
          e.object.matrix
        ), ke(
          H * (e.object.top - e.object.bottom) / e.object.zoom / y.clientHeight,
          e.object.matrix
        )) : (console.warn("WARNING: OrbitControls.js encountered an unknown camera type - pan disabled."), e.enablePan = !1);
      };
    })();
    function ge(l) {
      e.object instanceof me && e.object.isPerspectiveCamera || e.object instanceof fe && e.object.isOrthographicCamera ? u = l : (console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."), e.enableZoom = !1);
    }
    function le(l) {
      ge(u / l);
    }
    function Ie(l) {
      ge(u * l);
    }
    function je(l) {
      if (!e.zoomToCursor || !e.domElement)
        return;
      L = !0;
      const f = e.domElement.getBoundingClientRect(), I = l.clientX - f.left, H = l.clientY - f.top, y = f.width, U = f.height;
      P.x = I / y * 2 - 1, P.y = -(H / U) * 2 + 1, O.set(P.x, P.y, 1).unproject(e.object).sub(e.object.position).normalize();
    }
    function Re(l) {
      return Math.max(e.minDistance, Math.min(e.maxDistance, l));
    }
    function Xe(l) {
      d.set(l.clientX, l.clientY);
    }
    function Jt(l) {
      je(l), g.set(l.clientX, l.clientY);
    }
    function Ye(l) {
      E.set(l.clientX, l.clientY);
    }
    function yt(l) {
      p.set(l.clientX, l.clientY), m.subVectors(p, d).multiplyScalar(e.rotateSpeed);
      const f = e.domElement;
      f && (De(2 * Math.PI * m.x / f.clientHeight), _e(2 * Math.PI * m.y / f.clientHeight)), d.copy(p), e.update();
    }
    function Ot(l) {
      R.set(l.clientX, l.clientY), M.subVectors(R, g), M.y > 0 ? le(Y()) : M.y < 0 && Ie(Y()), g.copy(R), e.update();
    }
    function Pt(l) {
      G.set(l.clientX, l.clientY), D.subVectors(G, E).multiplyScalar(e.panSpeed), q(D.x, D.y), E.copy(G), e.update();
    }
    function St(l) {
      je(l), l.deltaY < 0 ? Ie(Y()) : l.deltaY > 0 && le(Y()), e.update();
    }
    function xt(l) {
      let f = !1;
      switch (l.code) {
        case e.keys.UP:
          q(0, e.keyPanSpeed), f = !0;
          break;
        case e.keys.BOTTOM:
          q(0, -e.keyPanSpeed), f = !0;
          break;
        case e.keys.LEFT:
          q(e.keyPanSpeed, 0), f = !0;
          break;
        case e.keys.RIGHT:
          q(-e.keyPanSpeed, 0), f = !0;
          break;
      }
      f && (l.preventDefault(), e.update());
    }
    function Ze() {
      if (b.length == 1)
        d.set(b[0].pageX, b[0].pageY);
      else {
        const l = 0.5 * (b[0].pageX + b[1].pageX), f = 0.5 * (b[0].pageY + b[1].pageY);
        d.set(l, f);
      }
    }
    function We() {
      if (b.length == 1)
        E.set(b[0].pageX, b[0].pageY);
      else {
        const l = 0.5 * (b[0].pageX + b[1].pageX), f = 0.5 * (b[0].pageY + b[1].pageY);
        E.set(l, f);
      }
    }
    function Ve() {
      const l = b[0].pageX - b[1].pageX, f = b[0].pageY - b[1].pageY, I = Math.sqrt(l * l + f * f);
      g.set(0, I);
    }
    function Kt() {
      e.enableZoom && Ve(), e.enablePan && We();
    }
    function Ut() {
      e.enableZoom && Ve(), e.enableRotate && Ze();
    }
    function qe(l) {
      if (b.length == 1)
        p.set(l.pageX, l.pageY);
      else {
        const I = He(l), H = 0.5 * (l.pageX + I.x), y = 0.5 * (l.pageY + I.y);
        p.set(H, y);
      }
      m.subVectors(p, d).multiplyScalar(e.rotateSpeed);
      const f = e.domElement;
      f && (De(2 * Math.PI * m.x / f.clientHeight), _e(2 * Math.PI * m.y / f.clientHeight)), d.copy(p);
    }
    function ze(l) {
      if (b.length == 1)
        G.set(l.pageX, l.pageY);
      else {
        const f = He(l), I = 0.5 * (l.pageX + f.x), H = 0.5 * (l.pageY + f.y);
        G.set(I, H);
      }
      D.subVectors(G, E).multiplyScalar(e.panSpeed), q(D.x, D.y), E.copy(G);
    }
    function $e(l) {
      const f = He(l), I = l.pageX - f.x, H = l.pageY - f.y, y = Math.sqrt(I * I + H * H);
      R.set(0, y), M.set(0, Math.pow(R.y / g.y, e.zoomSpeed)), le(M.y), g.copy(R);
    }
    function Nt(l) {
      e.enableZoom && $e(l), e.enablePan && ze(l);
    }
    function wt(l) {
      e.enableZoom && $e(l), e.enableRotate && qe(l);
    }
    function et(l) {
      var f, I;
      e.enabled !== !1 && (b.length === 0 && ((f = e.domElement) == null || f.ownerDocument.addEventListener("pointermove", Te), (I = e.domElement) == null || I.ownerDocument.addEventListener("pointerup", te)), jt(l), l.pointerType === "touch" ? Qt(l) : vt(l));
    }
    function Te(l) {
      e.enabled !== !1 && (l.pointerType === "touch" ? kt(l) : _t(l));
    }
    function te(l) {
      var f, I, H;
      Xt(l), b.length === 0 && ((f = e.domElement) == null || f.releasePointerCapture(l.pointerId), (I = e.domElement) == null || I.ownerDocument.removeEventListener("pointermove", Te), (H = e.domElement) == null || H.ownerDocument.removeEventListener("pointerup", te)), e.dispatchEvent(r), i = a.NONE;
    }
    function vt(l) {
      let f;
      switch (l.button) {
        case 0:
          f = e.mouseButtons.LEFT;
          break;
        case 1:
          f = e.mouseButtons.MIDDLE;
          break;
        case 2:
          f = e.mouseButtons.RIGHT;
          break;
        default:
          f = -1;
      }
      switch (f) {
        case z.DOLLY:
          if (e.enableZoom === !1)
            return;
          Jt(l), i = a.DOLLY;
          break;
        case z.ROTATE:
          if (l.ctrlKey || l.metaKey || l.shiftKey) {
            if (e.enablePan === !1)
              return;
            Ye(l), i = a.PAN;
          } else {
            if (e.enableRotate === !1)
              return;
            Xe(l), i = a.ROTATE;
          }
          break;
        case z.PAN:
          if (l.ctrlKey || l.metaKey || l.shiftKey) {
            if (e.enableRotate === !1)
              return;
            Xe(l), i = a.ROTATE;
          } else {
            if (e.enablePan === !1)
              return;
            Ye(l), i = a.PAN;
          }
          break;
        default:
          i = a.NONE;
      }
      i !== a.NONE && e.dispatchEvent(o);
    }
    function _t(l) {
      if (e.enabled !== !1)
        switch (i) {
          case a.ROTATE:
            if (e.enableRotate === !1)
              return;
            yt(l);
            break;
          case a.DOLLY:
            if (e.enableZoom === !1)
              return;
            Ot(l);
            break;
          case a.PAN:
            if (e.enablePan === !1)
              return;
            Pt(l);
            break;
        }
    }
    function tt(l) {
      e.enabled === !1 || e.enableZoom === !1 || i !== a.NONE && i !== a.ROTATE || (l.preventDefault(), e.dispatchEvent(o), St(l), e.dispatchEvent(r));
    }
    function be(l) {
      e.enabled === !1 || e.enablePan === !1 || xt(l);
    }
    function Qt(l) {
      switch (nt(l), b.length) {
        case 1:
          switch (e.touches.ONE) {
            case $.ROTATE:
              if (e.enableRotate === !1)
                return;
              Ze(), i = a.TOUCH_ROTATE;
              break;
            case $.PAN:
              if (e.enablePan === !1)
                return;
              We(), i = a.TOUCH_PAN;
              break;
            default:
              i = a.NONE;
          }
          break;
        case 2:
          switch (e.touches.TWO) {
            case $.DOLLY_PAN:
              if (e.enableZoom === !1 && e.enablePan === !1)
                return;
              Kt(), i = a.TOUCH_DOLLY_PAN;
              break;
            case $.DOLLY_ROTATE:
              if (e.enableZoom === !1 && e.enableRotate === !1)
                return;
              Ut(), i = a.TOUCH_DOLLY_ROTATE;
              break;
            default:
              i = a.NONE;
          }
          break;
        default:
          i = a.NONE;
      }
      i !== a.NONE && e.dispatchEvent(o);
    }
    function kt(l) {
      switch (nt(l), i) {
        case a.TOUCH_ROTATE:
          if (e.enableRotate === !1)
            return;
          qe(l), e.update();
          break;
        case a.TOUCH_PAN:
          if (e.enablePan === !1)
            return;
          ze(l), e.update();
          break;
        case a.TOUCH_DOLLY_PAN:
          if (e.enableZoom === !1 && e.enablePan === !1)
            return;
          Nt(l), e.update();
          break;
        case a.TOUCH_DOLLY_ROTATE:
          if (e.enableZoom === !1 && e.enableRotate === !1)
            return;
          wt(l), e.update();
          break;
        default:
          i = a.NONE;
      }
    }
    function st(l) {
      e.enabled !== !1 && l.preventDefault();
    }
    function jt(l) {
      b.push(l);
    }
    function Xt(l) {
      delete Be[l.pointerId];
      for (let f = 0; f < b.length; f++)
        if (b[f].pointerId == l.pointerId) {
          b.splice(f, 1);
          return;
        }
    }
    function nt(l) {
      let f = Be[l.pointerId];
      f === void 0 && (f = new S(), Be[l.pointerId] = f), f.set(l.pageX, l.pageY);
    }
    function He(l) {
      const f = l.pointerId === b[0].pointerId ? b[1] : b[0];
      return Be[f.pointerId];
    }
    this.dollyIn = (l = Y()) => {
      Ie(l), e.update();
    }, this.dollyOut = (l = Y()) => {
      le(l), e.update();
    }, this.getScale = () => u, this.setScale = (l) => {
      ge(l), e.update();
    }, this.getZoomScale = () => Y(), s !== void 0 && this.connect(s), this.update();
  }
};
function Fe(h) {
  if (typeof TextDecoder < "u")
    return new TextDecoder().decode(h);
  let t = "";
  for (let s = 0, e = h.length; s < e; s++)
    t += String.fromCharCode(h[s]);
  try {
    return decodeURIComponent(escape(t));
  } catch {
    return t;
  }
}
const W = "srgb", _ = "srgb-linear", ht = 3001, _s = 3e3;
class ve extends pt {
  constructor(t) {
    super(t), this.dracoLoader = null, this.ktx2Loader = null, this.meshoptDecoder = null, this.pluginCallbacks = [], this.register(function(s) {
      return new Ys(s);
    }), this.register(function(s) {
      return new Zs(s);
    }), this.register(function(s) {
      return new nn(s);
    }), this.register(function(s) {
      return new on(s);
    }), this.register(function(s) {
      return new rn(s);
    }), this.register(function(s) {
      return new Vs(s);
    }), this.register(function(s) {
      return new qs(s);
    }), this.register(function(s) {
      return new zs(s);
    }), this.register(function(s) {
      return new $s(s);
    }), this.register(function(s) {
      return new Xs(s);
    }), this.register(function(s) {
      return new en(s);
    }), this.register(function(s) {
      return new Ws(s);
    }), this.register(function(s) {
      return new sn(s);
    }), this.register(function(s) {
      return new tn(s);
    }), this.register(function(s) {
      return new ks(s);
    }), this.register(function(s) {
      return new an(s);
    }), this.register(function(s) {
      return new An(s);
    });
  }
  load(t, s, e, n) {
    const o = this;
    let r;
    if (this.resourcePath !== "")
      r = this.resourcePath;
    else if (this.path !== "") {
      const A = Ae.extractUrlBase(t);
      r = Ae.resolveURL(A, this.path);
    } else
      r = Ae.extractUrlBase(t);
    this.manager.itemStart(t);
    const a = function(A) {
      n ? n(A) : console.error(A), o.manager.itemError(t), o.manager.itemEnd(t);
    }, i = new Ee(this.manager);
    i.setPath(this.path), i.setResponseType("arraybuffer"), i.setRequestHeader(this.requestHeader), i.setWithCredentials(this.withCredentials), i.load(
      t,
      function(A) {
        try {
          o.parse(
            A,
            r,
            function(B) {
              s(B), o.manager.itemEnd(t);
            },
            a
          );
        } catch (B) {
          a(B);
        }
      },
      e,
      a
    );
  }
  setDRACOLoader(t) {
    return this.dracoLoader = t, this;
  }
  setDDSLoader() {
    throw new Error('THREE.GLTFLoader: "MSFT_texture_dds" no longer supported. Please update to "KHR_texture_basisu".');
  }
  setKTX2Loader(t) {
    return this.ktx2Loader = t, this;
  }
  setMeshoptDecoder(t) {
    return this.meshoptDecoder = t, this;
  }
  register(t) {
    return this.pluginCallbacks.indexOf(t) === -1 && this.pluginCallbacks.push(t), this;
  }
  unregister(t) {
    return this.pluginCallbacks.indexOf(t) !== -1 && this.pluginCallbacks.splice(this.pluginCallbacks.indexOf(t), 1), this;
  }
  parse(t, s, e, n) {
    let o;
    const r = {}, a = {};
    if (typeof t == "string")
      o = JSON.parse(t);
    else if (t instanceof ArrayBuffer)
      if (Fe(new Uint8Array(t.slice(0, 4))) === Rt) {
        try {
          r[T.KHR_BINARY_GLTF] = new cn(t);
        } catch (B) {
          n && n(B);
          return;
        }
        o = JSON.parse(r[T.KHR_BINARY_GLTF].content);
      } else
        o = JSON.parse(Fe(new Uint8Array(t)));
    else
      o = t;
    if (o.asset === void 0 || o.asset.version[0] < 2) {
      n && n(new Error("THREE.GLTFLoader: Unsupported asset. glTF versions >=2.0 are supported."));
      return;
    }
    const i = new Gn(o, {
      path: s || this.resourcePath || "",
      crossOrigin: this.crossOrigin,
      requestHeader: this.requestHeader,
      manager: this.manager,
      ktx2Loader: this.ktx2Loader,
      meshoptDecoder: this.meshoptDecoder
    });
    i.fileLoader.setRequestHeader(this.requestHeader);
    for (let A = 0; A < this.pluginCallbacks.length; A++) {
      const B = this.pluginCallbacks[A](i);
      B.name || console.error("THREE.GLTFLoader: Invalid plugin found: missing name"), a[B.name] = B, r[B.name] = !0;
    }
    if (o.extensionsUsed)
      for (let A = 0; A < o.extensionsUsed.length; ++A) {
        const B = o.extensionsUsed[A], c = o.extensionsRequired || [];
        switch (B) {
          case T.KHR_MATERIALS_UNLIT:
            r[B] = new js();
            break;
          case T.KHR_DRACO_MESH_COMPRESSION:
            r[B] = new Bn(o, this.dracoLoader);
            break;
          case T.KHR_TEXTURE_TRANSFORM:
            r[B] = new ln();
            break;
          case T.KHR_MESH_QUANTIZATION:
            r[B] = new un();
            break;
          default:
            c.indexOf(B) >= 0 && a[B] === void 0 && console.warn('THREE.GLTFLoader: Unknown extension "' + B + '".');
        }
      }
    i.setExtensions(r), i.setPlugins(a), i.parse(e, n);
  }
  parseAsync(t, s) {
    const e = this;
    return new Promise(function(n, o) {
      e.parse(t, s, n, o);
    });
  }
}
function Qs() {
  let h = {};
  return {
    get: function(t) {
      return h[t];
    },
    add: function(t, s) {
      h[t] = s;
    },
    remove: function(t) {
      delete h[t];
    },
    removeAll: function() {
      h = {};
    }
  };
}
const T = {
  KHR_BINARY_GLTF: "KHR_binary_glTF",
  KHR_DRACO_MESH_COMPRESSION: "KHR_draco_mesh_compression",
  KHR_LIGHTS_PUNCTUAL: "KHR_lights_punctual",
  KHR_MATERIALS_CLEARCOAT: "KHR_materials_clearcoat",
  KHR_MATERIALS_DISPERSION: "KHR_materials_dispersion",
  KHR_MATERIALS_IOR: "KHR_materials_ior",
  KHR_MATERIALS_SHEEN: "KHR_materials_sheen",
  KHR_MATERIALS_SPECULAR: "KHR_materials_specular",
  KHR_MATERIALS_TRANSMISSION: "KHR_materials_transmission",
  KHR_MATERIALS_IRIDESCENCE: "KHR_materials_iridescence",
  KHR_MATERIALS_ANISOTROPY: "KHR_materials_anisotropy",
  KHR_MATERIALS_UNLIT: "KHR_materials_unlit",
  KHR_MATERIALS_VOLUME: "KHR_materials_volume",
  KHR_TEXTURE_BASISU: "KHR_texture_basisu",
  KHR_TEXTURE_TRANSFORM: "KHR_texture_transform",
  KHR_MESH_QUANTIZATION: "KHR_mesh_quantization",
  KHR_MATERIALS_EMISSIVE_STRENGTH: "KHR_materials_emissive_strength",
  EXT_MATERIALS_BUMP: "EXT_materials_bump",
  EXT_TEXTURE_WEBP: "EXT_texture_webp",
  EXT_TEXTURE_AVIF: "EXT_texture_avif",
  EXT_MESHOPT_COMPRESSION: "EXT_meshopt_compression",
  EXT_MESH_GPU_INSTANCING: "EXT_mesh_gpu_instancing"
};
class ks {
  constructor(t) {
    this.parser = t, this.name = T.KHR_LIGHTS_PUNCTUAL, this.cache = { refs: {}, uses: {} };
  }
  _markDefs() {
    const t = this.parser, s = this.parser.json.nodes || [];
    for (let e = 0, n = s.length; e < n; e++) {
      const o = s[e];
      o.extensions && o.extensions[this.name] && o.extensions[this.name].light !== void 0 && t._addNodeRef(this.cache, o.extensions[this.name].light);
    }
  }
  _loadLight(t) {
    const s = this.parser, e = "light:" + t;
    let n = s.cache.get(e);
    if (n)
      return n;
    const o = s.json, i = ((o.extensions && o.extensions[this.name] || {}).lights || [])[t];
    let A;
    const B = new V(16777215);
    i.color !== void 0 && B.setRGB(i.color[0], i.color[1], i.color[2], _);
    const c = i.range !== void 0 ? i.range : 0;
    switch (i.type) {
      case "directional":
        A = new zt(B), A.target.position.set(0, 0, -1), A.add(A.target);
        break;
      case "point":
        A = new qt(B), A.distance = c;
        break;
      case "spot":
        A = new Vt(B), A.distance = c, i.spot = i.spot || {}, i.spot.innerConeAngle = i.spot.innerConeAngle !== void 0 ? i.spot.innerConeAngle : 0, i.spot.outerConeAngle = i.spot.outerConeAngle !== void 0 ? i.spot.outerConeAngle : Math.PI / 4, A.angle = i.spot.outerConeAngle, A.penumbra = 1 - i.spot.innerConeAngle / i.spot.outerConeAngle, A.target.position.set(0, 0, -1), A.add(A.target);
        break;
      default:
        throw new Error("THREE.GLTFLoader: Unexpected light type: " + i.type);
    }
    return A.position.set(0, 0, 0), A.decay = 2, v(A, i), i.intensity !== void 0 && (A.intensity = i.intensity), A.name = s.createUniqueName(i.name || "light_" + t), n = Promise.resolve(A), s.cache.add(e, n), n;
  }
  getDependency(t, s) {
    if (t === "light")
      return this._loadLight(s);
  }
  createNodeAttachment(t) {
    const s = this, e = this.parser, o = e.json.nodes[t], a = (o.extensions && o.extensions[this.name] || {}).light;
    return a === void 0 ? null : this._loadLight(a).then(function(i) {
      return e._getNodeRef(s.cache, a, i);
    });
  }
}
class js {
  constructor() {
    this.name = T.KHR_MATERIALS_UNLIT;
  }
  getMaterialType() {
    return ae;
  }
  extendParams(t, s, e) {
    const n = [];
    t.color = new V(1, 1, 1), t.opacity = 1;
    const o = s.pbrMetallicRoughness;
    if (o) {
      if (Array.isArray(o.baseColorFactor)) {
        const r = o.baseColorFactor;
        t.color.setRGB(r[0], r[1], r[2], _), t.opacity = r[3];
      }
      o.baseColorTexture !== void 0 && n.push(e.assignTexture(t, "map", o.baseColorTexture, W));
    }
    return Promise.all(n);
  }
}
class Xs {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_EMISSIVE_STRENGTH;
  }
  extendMaterialParams(t, s) {
    const n = this.parser.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = n.extensions[this.name].emissiveStrength;
    return o !== void 0 && (s.emissiveIntensity = o), Promise.resolve();
  }
}
class Ys {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_CLEARCOAT;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const e = this.parser, n = e.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = [], r = n.extensions[this.name];
    if (r.clearcoatFactor !== void 0 && (s.clearcoat = r.clearcoatFactor), r.clearcoatTexture !== void 0 && o.push(e.assignTexture(s, "clearcoatMap", r.clearcoatTexture)), r.clearcoatRoughnessFactor !== void 0 && (s.clearcoatRoughness = r.clearcoatRoughnessFactor), r.clearcoatRoughnessTexture !== void 0 && o.push(e.assignTexture(s, "clearcoatRoughnessMap", r.clearcoatRoughnessTexture)), r.clearcoatNormalTexture !== void 0 && (o.push(e.assignTexture(s, "clearcoatNormalMap", r.clearcoatNormalTexture)), r.clearcoatNormalTexture.scale !== void 0)) {
      const a = r.clearcoatNormalTexture.scale;
      s.clearcoatNormalScale = new S(a, a);
    }
    return Promise.all(o);
  }
}
class Zs {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_DISPERSION;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const n = this.parser.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = n.extensions[this.name];
    return s.dispersion = o.dispersion !== void 0 ? o.dispersion : 0, Promise.resolve();
  }
}
class Ws {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_IRIDESCENCE;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const e = this.parser, n = e.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = [], r = n.extensions[this.name];
    return r.iridescenceFactor !== void 0 && (s.iridescence = r.iridescenceFactor), r.iridescenceTexture !== void 0 && o.push(e.assignTexture(s, "iridescenceMap", r.iridescenceTexture)), r.iridescenceIor !== void 0 && (s.iridescenceIOR = r.iridescenceIor), s.iridescenceThicknessRange === void 0 && (s.iridescenceThicknessRange = [100, 400]), r.iridescenceThicknessMinimum !== void 0 && (s.iridescenceThicknessRange[0] = r.iridescenceThicknessMinimum), r.iridescenceThicknessMaximum !== void 0 && (s.iridescenceThicknessRange[1] = r.iridescenceThicknessMaximum), r.iridescenceThicknessTexture !== void 0 && o.push(
      e.assignTexture(s, "iridescenceThicknessMap", r.iridescenceThicknessTexture)
    ), Promise.all(o);
  }
}
class Vs {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_SHEEN;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const e = this.parser, n = e.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = [];
    s.sheenColor = new V(0, 0, 0), s.sheenRoughness = 0, s.sheen = 1;
    const r = n.extensions[this.name];
    if (r.sheenColorFactor !== void 0) {
      const a = r.sheenColorFactor;
      s.sheenColor.setRGB(a[0], a[1], a[2], _);
    }
    return r.sheenRoughnessFactor !== void 0 && (s.sheenRoughness = r.sheenRoughnessFactor), r.sheenColorTexture !== void 0 && o.push(e.assignTexture(s, "sheenColorMap", r.sheenColorTexture, W)), r.sheenRoughnessTexture !== void 0 && o.push(e.assignTexture(s, "sheenRoughnessMap", r.sheenRoughnessTexture)), Promise.all(o);
  }
}
class qs {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_TRANSMISSION;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const e = this.parser, n = e.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = [], r = n.extensions[this.name];
    return r.transmissionFactor !== void 0 && (s.transmission = r.transmissionFactor), r.transmissionTexture !== void 0 && o.push(e.assignTexture(s, "transmissionMap", r.transmissionTexture)), Promise.all(o);
  }
}
class zs {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_VOLUME;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const e = this.parser, n = e.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = [], r = n.extensions[this.name];
    s.thickness = r.thicknessFactor !== void 0 ? r.thicknessFactor : 0, r.thicknessTexture !== void 0 && o.push(e.assignTexture(s, "thicknessMap", r.thicknessTexture)), s.attenuationDistance = r.attenuationDistance || 1 / 0;
    const a = r.attenuationColor || [1, 1, 1];
    return s.attenuationColor = new V().setRGB(
      a[0],
      a[1],
      a[2],
      _
    ), Promise.all(o);
  }
}
class $s {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_IOR;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const n = this.parser.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = n.extensions[this.name];
    return s.ior = o.ior !== void 0 ? o.ior : 1.5, Promise.resolve();
  }
}
class en {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_SPECULAR;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const e = this.parser, n = e.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = [], r = n.extensions[this.name];
    s.specularIntensity = r.specularFactor !== void 0 ? r.specularFactor : 1, r.specularTexture !== void 0 && o.push(e.assignTexture(s, "specularIntensityMap", r.specularTexture));
    const a = r.specularColorFactor || [1, 1, 1];
    return s.specularColor = new V().setRGB(a[0], a[1], a[2], _), r.specularColorTexture !== void 0 && o.push(
      e.assignTexture(s, "specularColorMap", r.specularColorTexture, W)
    ), Promise.all(o);
  }
}
class tn {
  constructor(t) {
    this.parser = t, this.name = T.EXT_MATERIALS_BUMP;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const e = this.parser, n = e.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = [], r = n.extensions[this.name];
    return s.bumpScale = r.bumpFactor !== void 0 ? r.bumpFactor : 1, r.bumpTexture !== void 0 && o.push(e.assignTexture(s, "bumpMap", r.bumpTexture)), Promise.all(o);
  }
}
class sn {
  constructor(t) {
    this.parser = t, this.name = T.KHR_MATERIALS_ANISOTROPY;
  }
  getMaterialType(t) {
    const e = this.parser.json.materials[t];
    return !e.extensions || !e.extensions[this.name] ? null : K;
  }
  extendMaterialParams(t, s) {
    const e = this.parser, n = e.json.materials[t];
    if (!n.extensions || !n.extensions[this.name])
      return Promise.resolve();
    const o = [], r = n.extensions[this.name];
    return r.anisotropyStrength !== void 0 && (s.anisotropy = r.anisotropyStrength), r.anisotropyRotation !== void 0 && (s.anisotropyRotation = r.anisotropyRotation), r.anisotropyTexture !== void 0 && o.push(e.assignTexture(s, "anisotropyMap", r.anisotropyTexture)), Promise.all(o);
  }
}
class nn {
  constructor(t) {
    this.parser = t, this.name = T.KHR_TEXTURE_BASISU;
  }
  loadTexture(t) {
    const s = this.parser, e = s.json, n = e.textures[t];
    if (!n.extensions || !n.extensions[this.name])
      return null;
    const o = n.extensions[this.name], r = s.options.ktx2Loader;
    if (!r) {
      if (e.extensionsRequired && e.extensionsRequired.indexOf(this.name) >= 0)
        throw new Error("THREE.GLTFLoader: setKTX2Loader must be called before loading KTX2 textures");
      return null;
    }
    return s.loadTextureImage(t, o.source, r);
  }
}
class on {
  constructor(t) {
    this.parser = t, this.name = T.EXT_TEXTURE_WEBP, this.isSupported = null;
  }
  loadTexture(t) {
    const s = this.name, e = this.parser, n = e.json, o = n.textures[t];
    if (!o.extensions || !o.extensions[s])
      return null;
    const r = o.extensions[s], a = n.images[r.source];
    let i = e.textureLoader;
    if (a.uri) {
      const A = e.options.manager.getHandler(a.uri);
      A !== null && (i = A);
    }
    return this.detectSupport().then(function(A) {
      if (A)
        return e.loadTextureImage(t, r.source, i);
      if (n.extensionsRequired && n.extensionsRequired.indexOf(s) >= 0)
        throw new Error("THREE.GLTFLoader: WebP required by asset but unsupported.");
      return e.loadTexture(t);
    });
  }
  detectSupport() {
    return this.isSupported || (this.isSupported = new Promise(function(t) {
      const s = new Image();
      s.src = "data:image/webp;base64,UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA", s.onload = s.onerror = function() {
        t(s.height === 1);
      };
    })), this.isSupported;
  }
}
class rn {
  constructor(t) {
    this.parser = t, this.name = T.EXT_TEXTURE_AVIF, this.isSupported = null;
  }
  loadTexture(t) {
    const s = this.name, e = this.parser, n = e.json, o = n.textures[t];
    if (!o.extensions || !o.extensions[s])
      return null;
    const r = o.extensions[s], a = n.images[r.source];
    let i = e.textureLoader;
    if (a.uri) {
      const A = e.options.manager.getHandler(a.uri);
      A !== null && (i = A);
    }
    return this.detectSupport().then(function(A) {
      if (A)
        return e.loadTextureImage(t, r.source, i);
      if (n.extensionsRequired && n.extensionsRequired.indexOf(s) >= 0)
        throw new Error("THREE.GLTFLoader: AVIF required by asset but unsupported.");
      return e.loadTexture(t);
    });
  }
  detectSupport() {
    return this.isSupported || (this.isSupported = new Promise(function(t) {
      const s = new Image();
      s.src = "data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAABcAAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAEAAAABAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQAMAAAAABNjb2xybmNseAACAAIABoAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAAB9tZGF0EgAKCBgABogQEDQgMgkQAAAAB8dSLfI=", s.onload = s.onerror = function() {
        t(s.height === 1);
      };
    })), this.isSupported;
  }
}
class an {
  constructor(t) {
    this.name = T.EXT_MESHOPT_COMPRESSION, this.parser = t;
  }
  loadBufferView(t) {
    const s = this.parser.json, e = s.bufferViews[t];
    if (e.extensions && e.extensions[this.name]) {
      const n = e.extensions[this.name], o = this.parser.getDependency("buffer", n.buffer), r = this.parser.options.meshoptDecoder;
      if (!r || !r.supported) {
        if (s.extensionsRequired && s.extensionsRequired.indexOf(this.name) >= 0)
          throw new Error("THREE.GLTFLoader: setMeshoptDecoder must be called before loading compressed files");
        return null;
      }
      return o.then(function(a) {
        const i = n.byteOffset || 0, A = n.byteLength || 0, B = n.count, c = n.byteStride, u = new Uint8Array(a, i, A);
        return r.decodeGltfBufferAsync ? r.decodeGltfBufferAsync(B, c, u, n.mode, n.filter).then(function(C) {
          return C.buffer;
        }) : r.ready.then(function() {
          const C = new ArrayBuffer(B * c);
          return r.decodeGltfBuffer(
            new Uint8Array(C),
            B,
            c,
            u,
            n.mode,
            n.filter
          ), C;
        });
      });
    } else
      return null;
  }
}
class An {
  constructor(t) {
    this.name = T.EXT_MESH_GPU_INSTANCING, this.parser = t;
  }
  createNodeMesh(t) {
    const s = this.parser.json, e = s.nodes[t];
    if (!e.extensions || !e.extensions[this.name] || e.mesh === void 0)
      return null;
    const n = s.meshes[e.mesh];
    for (const A of n.primitives)
      if (A.mode !== x.TRIANGLES && A.mode !== x.TRIANGLE_STRIP && A.mode !== x.TRIANGLE_FAN && A.mode !== void 0)
        return null;
    const r = e.extensions[this.name].attributes, a = [], i = {};
    for (const A in r)
      a.push(
        this.parser.getDependency("accessor", r[A]).then((B) => (i[A] = B, i[A]))
      );
    return a.length < 1 ? null : (a.push(this.parser.createNodeMesh(t)), Promise.all(a).then((A) => {
      const B = A.pop(), c = B.isGroup ? B.children : [B], u = A[0].count, C = [];
      for (const d of c) {
        const p = new Me(), m = new J(), E = new pe(), G = new J(1, 1, 1), D = new $t(d.geometry, d.material, u);
        for (let g = 0; g < u; g++)
          i.TRANSLATION && m.fromBufferAttribute(i.TRANSLATION, g), i.ROTATION && E.fromBufferAttribute(i.ROTATION, g), i.SCALE && G.fromBufferAttribute(i.SCALE, g), D.setMatrixAt(g, p.compose(m, E, G));
        for (const g in i)
          if (g === "_COLOR_0") {
            const R = i[g];
            D.instanceColor = new es(R.array, R.itemSize, R.normalized);
          } else g !== "TRANSLATION" && g !== "ROTATION" && g !== "SCALE" && d.geometry.setAttribute(g, i[g]);
        Et.prototype.copy.call(D, d), this.parser.assignFinalMaterial(D), C.push(D);
      }
      return B.isGroup ? (B.clear(), B.add(...C), B) : C[0];
    }));
  }
}
const Rt = "glTF", ie = 12, Ct = { JSON: 1313821514, BIN: 5130562 };
class cn {
  constructor(t) {
    this.name = T.KHR_BINARY_GLTF, this.content = null, this.body = null;
    const s = new DataView(t, 0, ie);
    if (this.header = {
      magic: Fe(new Uint8Array(t.slice(0, 4))),
      version: s.getUint32(4, !0),
      length: s.getUint32(8, !0)
    }, this.header.magic !== Rt)
      throw new Error("THREE.GLTFLoader: Unsupported glTF-Binary header.");
    if (this.header.version < 2)
      throw new Error("THREE.GLTFLoader: Legacy binary file detected.");
    const e = this.header.length - ie, n = new DataView(t, ie);
    let o = 0;
    for (; o < e; ) {
      const r = n.getUint32(o, !0);
      o += 4;
      const a = n.getUint32(o, !0);
      if (o += 4, a === Ct.JSON) {
        const i = new Uint8Array(t, ie + o, r);
        this.content = Fe(i);
      } else if (a === Ct.BIN) {
        const i = ie + o;
        this.body = t.slice(i, i + r);
      }
      o += r;
    }
    if (this.content === null)
      throw new Error("THREE.GLTFLoader: JSON content not found.");
  }
}
class Bn {
  constructor(t, s) {
    if (!s)
      throw new Error("THREE.GLTFLoader: No DRACOLoader instance provided.");
    this.name = T.KHR_DRACO_MESH_COMPRESSION, this.json = t, this.dracoLoader = s, this.dracoLoader.preload();
  }
  decodePrimitive(t, s) {
    const e = this.json, n = this.dracoLoader, o = t.extensions[this.name].bufferView, r = t.extensions[this.name].attributes, a = {}, i = {}, A = {};
    for (const B in r) {
      const c = Ue[B] || B.toLowerCase();
      a[c] = r[B];
    }
    for (const B in t.attributes) {
      const c = Ue[B] || B.toLowerCase();
      if (r[B] !== void 0) {
        const u = e.accessors[t.attributes[B]], C = ee[u.componentType];
        A[c] = C.name, i[c] = u.normalized === !0;
      }
    }
    return s.getDependency("bufferView", o).then(function(B) {
      return new Promise(function(c, u) {
        n.decodeDracoFile(
          B,
          function(C) {
            for (const d in C.attributes) {
              const p = C.attributes[d], m = i[d];
              m !== void 0 && (p.normalized = m);
            }
            c(C);
          },
          a,
          A,
          _,
          u
        );
      });
    });
  }
}
class ln {
  constructor() {
    this.name = T.KHR_TEXTURE_TRANSFORM;
  }
  extendTexture(t, s) {
    return (s.texCoord === void 0 || s.texCoord === t.channel) && s.offset === void 0 && s.rotation === void 0 && s.scale === void 0 || (t = t.clone(), s.texCoord !== void 0 && (t.channel = s.texCoord), s.offset !== void 0 && t.offset.fromArray(s.offset), s.rotation !== void 0 && (t.rotation = s.rotation), s.scale !== void 0 && t.repeat.fromArray(s.scale), t.needsUpdate = !0), t;
  }
}
class un {
  constructor() {
    this.name = T.KHR_MESH_QUANTIZATION;
  }
}
class Tt extends Ts {
  constructor(t, s, e, n) {
    super(t, s, e, n);
  }
  copySampleValue_(t) {
    const s = this.resultBuffer, e = this.sampleValues, n = this.valueSize, o = t * n * 3 + n;
    for (let r = 0; r !== n; r++)
      s[r] = e[o + r];
    return s;
  }
  interpolate_(t, s, e, n) {
    const o = this.resultBuffer, r = this.sampleValues, a = this.valueSize, i = a * 2, A = a * 3, B = n - s, c = (e - s) / B, u = c * c, C = u * c, d = t * A, p = d - A, m = -2 * C + 3 * u, E = C - u, G = 1 - m, D = E - u + c;
    for (let g = 0; g !== a; g++) {
      const R = r[p + g + a], M = r[p + g + i] * B, O = r[d + g + a], P = r[d + g] * B;
      o[g] = G * R + D * M + m * O + E * P;
    }
    return o;
  }
}
const hn = /* @__PURE__ */ new pe();
class Cn extends Tt {
  interpolate_(t, s, e, n) {
    const o = super.interpolate_(t, s, e, n);
    return hn.fromArray(o).normalize().toArray(o), o;
  }
}
const x = {
  POINTS: 0,
  LINES: 1,
  LINE_LOOP: 2,
  LINE_STRIP: 3,
  TRIANGLES: 4,
  TRIANGLE_STRIP: 5,
  TRIANGLE_FAN: 6
}, ee = {
  5120: Int8Array,
  5121: Uint8Array,
  5122: Int16Array,
  5123: Uint16Array,
  5125: Uint32Array,
  5126: Float32Array
}, dt = {
  9728: as,
  9729: Ft,
  9984: is,
  9985: rs,
  9986: os,
  9987: Mt
}, ft = {
  33071: cs,
  33648: As,
  10497: Ke
}, ye = {
  SCALAR: 1,
  VEC2: 2,
  VEC3: 3,
  VEC4: 4,
  MAT2: 4,
  MAT3: 9,
  MAT4: 16
}, Ue = {
  POSITION: "position",
  NORMAL: "normal",
  TANGENT: "tangent",
  // uv => uv1, 4 uv channels
  // https://github.com/mrdoob/three.js/pull/25943
  // https://github.com/mrdoob/three.js/pull/25788
  ...Os >= 152 ? {
    TEXCOORD_0: "uv",
    TEXCOORD_1: "uv1",
    TEXCOORD_2: "uv2",
    TEXCOORD_3: "uv3"
  } : {
    TEXCOORD_0: "uv",
    TEXCOORD_1: "uv2"
  },
  COLOR_0: "color",
  WEIGHTS_0: "skinWeight",
  JOINTS_0: "skinIndex"
}, j = {
  scale: "scale",
  translation: "position",
  rotation: "quaternion",
  weights: "morphTargetInfluences"
}, dn = {
  CUBICSPLINE: void 0,
  // We use a custom interpolant (GLTFCubicSplineInterpolation) for CUBICSPLINE tracks. Each
  // keyframe track will be initialized with a default interpolation type, then modified.
  LINEAR: gt,
  STEP: gs
}, Oe = {
  OPAQUE: "OPAQUE",
  MASK: "MASK",
  BLEND: "BLEND"
};
function fn(h) {
  return h.DefaultMaterial === void 0 && (h.DefaultMaterial = new Gt({
    color: 16777215,
    emissive: 0,
    metalness: 1,
    roughness: 1,
    transparent: !1,
    depthTest: !0,
    side: Rs
  })), h.DefaultMaterial;
}
function Z(h, t, s) {
  for (const e in s.extensions)
    h[e] === void 0 && (t.userData.gltfExtensions = t.userData.gltfExtensions || {}, t.userData.gltfExtensions[e] = s.extensions[e]);
}
function v(h, t) {
  t.extras !== void 0 && (typeof t.extras == "object" ? Object.assign(h.userData, t.extras) : console.warn("THREE.GLTFLoader: Ignoring primitive type .extras, " + t.extras));
}
function mn(h, t, s) {
  let e = !1, n = !1, o = !1;
  for (let A = 0, B = t.length; A < B; A++) {
    const c = t[A];
    if (c.POSITION !== void 0 && (e = !0), c.NORMAL !== void 0 && (n = !0), c.COLOR_0 !== void 0 && (o = !0), e && n && o)
      break;
  }
  if (!e && !n && !o)
    return Promise.resolve(h);
  const r = [], a = [], i = [];
  for (let A = 0, B = t.length; A < B; A++) {
    const c = t[A];
    if (e) {
      const u = c.POSITION !== void 0 ? s.getDependency("accessor", c.POSITION) : h.attributes.position;
      r.push(u);
    }
    if (n) {
      const u = c.NORMAL !== void 0 ? s.getDependency("accessor", c.NORMAL) : h.attributes.normal;
      a.push(u);
    }
    if (o) {
      const u = c.COLOR_0 !== void 0 ? s.getDependency("accessor", c.COLOR_0) : h.attributes.color;
      i.push(u);
    }
  }
  return Promise.all([
    Promise.all(r),
    Promise.all(a),
    Promise.all(i)
  ]).then(function(A) {
    const B = A[0], c = A[1], u = A[2];
    return e && (h.morphAttributes.position = B), n && (h.morphAttributes.normal = c), o && (h.morphAttributes.color = u), h.morphTargetsRelative = !0, h;
  });
}
function pn(h, t) {
  if (h.updateMorphTargets(), t.weights !== void 0)
    for (let s = 0, e = t.weights.length; s < e; s++)
      h.morphTargetInfluences[s] = t.weights[s];
  if (t.extras && Array.isArray(t.extras.targetNames)) {
    const s = t.extras.targetNames;
    if (h.morphTargetInfluences.length === s.length) {
      h.morphTargetDictionary = {};
      for (let e = 0, n = s.length; e < n; e++)
        h.morphTargetDictionary[s[e]] = e;
    } else
      console.warn("THREE.GLTFLoader: Invalid extras.targetNames length. Ignoring names.");
  }
}
function En(h) {
  let t;
  const s = h.extensions && h.extensions[T.KHR_DRACO_MESH_COMPRESSION];
  if (s ? t = "draco:" + s.bufferView + ":" + s.indices + ":" + Pe(s.attributes) : t = h.indices + ":" + Pe(h.attributes) + ":" + h.mode, h.targets !== void 0)
    for (let e = 0, n = h.targets.length; e < n; e++)
      t += ":" + Pe(h.targets[e]);
  return t;
}
function Pe(h) {
  let t = "";
  const s = Object.keys(h).sort();
  for (let e = 0, n = s.length; e < n; e++)
    t += s[e] + ":" + h[s[e]] + ";";
  return t;
}
function Ne(h) {
  switch (h) {
    case Int8Array:
      return 1 / 127;
    case Uint8Array:
      return 1 / 255;
    case Int16Array:
      return 1 / 32767;
    case Uint16Array:
      return 1 / 65535;
    default:
      throw new Error("THREE.GLTFLoader: Unsupported normalized accessor component type.");
  }
}
function Mn(h) {
  return h.search(/\.jpe?g($|\?)/i) > 0 || h.search(/^data\:image\/jpeg/) === 0 ? "image/jpeg" : h.search(/\.webp($|\?)/i) > 0 || h.search(/^data\:image\/webp/) === 0 ? "image/webp" : "image/png";
}
const Fn = /* @__PURE__ */ new Me();
class Gn {
  constructor(t = {}, s = {}) {
    this.json = t, this.extensions = {}, this.plugins = {}, this.options = s, this.cache = new Qs(), this.associations = /* @__PURE__ */ new Map(), this.primitiveCache = {}, this.nodeCache = {}, this.meshCache = { refs: {}, uses: {} }, this.cameraCache = { refs: {}, uses: {} }, this.lightCache = { refs: {}, uses: {} }, this.sourceCache = {}, this.textureCache = {}, this.nodeNamesUsed = {};
    let e = !1, n = !1, o = -1;
    typeof navigator < "u" && typeof navigator.userAgent < "u" && (e = /^((?!chrome|android).)*safari/i.test(navigator.userAgent) === !0, n = navigator.userAgent.indexOf("Firefox") > -1, o = n ? navigator.userAgent.match(/Firefox\/([0-9]+)\./)[1] : -1), typeof createImageBitmap > "u" || e || n && o < 98 ? this.textureLoader = new ts(this.options.manager) : this.textureLoader = new ss(this.options.manager), this.textureLoader.setCrossOrigin(this.options.crossOrigin), this.textureLoader.setRequestHeader(this.options.requestHeader), this.fileLoader = new Ee(this.options.manager), this.fileLoader.setResponseType("arraybuffer"), this.options.crossOrigin === "use-credentials" && this.fileLoader.setWithCredentials(!0);
  }
  setExtensions(t) {
    this.extensions = t;
  }
  setPlugins(t) {
    this.plugins = t;
  }
  parse(t, s) {
    const e = this, n = this.json, o = this.extensions;
    this.cache.removeAll(), this.nodeCache = {}, this._invokeAll(function(r) {
      return r._markDefs && r._markDefs();
    }), Promise.all(
      this._invokeAll(function(r) {
        return r.beforeRoot && r.beforeRoot();
      })
    ).then(function() {
      return Promise.all([
        e.getDependencies("scene"),
        e.getDependencies("animation"),
        e.getDependencies("camera")
      ]);
    }).then(function(r) {
      const a = {
        scene: r[0][n.scene || 0],
        scenes: r[0],
        animations: r[1],
        cameras: r[2],
        asset: n.asset,
        parser: e,
        userData: {}
      };
      return Z(o, a, n), v(a, n), Promise.all(
        e._invokeAll(function(i) {
          return i.afterRoot && i.afterRoot(a);
        })
      ).then(function() {
        for (const i of a.scenes)
          i.updateMatrixWorld();
        t(a);
      });
    }).catch(s);
  }
  /**
   * Marks the special nodes/meshes in json for efficient parse.
   */
  _markDefs() {
    const t = this.json.nodes || [], s = this.json.skins || [], e = this.json.meshes || [];
    for (let n = 0, o = s.length; n < o; n++) {
      const r = s[n].joints;
      for (let a = 0, i = r.length; a < i; a++)
        t[r[a]].isBone = !0;
    }
    for (let n = 0, o = t.length; n < o; n++) {
      const r = t[n];
      r.mesh !== void 0 && (this._addNodeRef(this.meshCache, r.mesh), r.skin !== void 0 && (e[r.mesh].isSkinnedMesh = !0)), r.camera !== void 0 && this._addNodeRef(this.cameraCache, r.camera);
    }
  }
  /**
   * Counts references to shared node / Object3D resources. These resources
   * can be reused, or "instantiated", at multiple nodes in the scene
   * hierarchy. Mesh, Camera, and Light instances are instantiated and must
   * be marked. Non-scenegraph resources (like Materials, Geometries, and
   * Textures) can be reused directly and are not marked here.
   *
   * Example: CesiumMilkTruck sample model reuses "Wheel" meshes.
   */
  _addNodeRef(t, s) {
    s !== void 0 && (t.refs[s] === void 0 && (t.refs[s] = t.uses[s] = 0), t.refs[s]++);
  }
  /** Returns a reference to a shared resource, cloning it if necessary. */
  _getNodeRef(t, s, e) {
    if (t.refs[s] <= 1)
      return e;
    const n = e.clone(), o = (r, a) => {
      const i = this.associations.get(r);
      i != null && this.associations.set(a, i);
      for (const [A, B] of r.children.entries())
        o(B, a.children[A]);
    };
    return o(e, n), n.name += "_instance_" + t.uses[s]++, n;
  }
  _invokeOne(t) {
    const s = Object.values(this.plugins);
    s.push(this);
    for (let e = 0; e < s.length; e++) {
      const n = t(s[e]);
      if (n)
        return n;
    }
    return null;
  }
  _invokeAll(t) {
    const s = Object.values(this.plugins);
    s.unshift(this);
    const e = [];
    for (let n = 0; n < s.length; n++) {
      const o = t(s[n]);
      o && e.push(o);
    }
    return e;
  }
  /**
   * Requests the specified dependency asynchronously, with caching.
   * @param {string} type
   * @param {number} index
   * @return {Promise<Object3D|Material|THREE.Texture|AnimationClip|ArrayBuffer|Object>}
   */
  getDependency(t, s) {
    const e = t + ":" + s;
    let n = this.cache.get(e);
    if (!n) {
      switch (t) {
        case "scene":
          n = this.loadScene(s);
          break;
        case "node":
          n = this._invokeOne(function(o) {
            return o.loadNode && o.loadNode(s);
          });
          break;
        case "mesh":
          n = this._invokeOne(function(o) {
            return o.loadMesh && o.loadMesh(s);
          });
          break;
        case "accessor":
          n = this.loadAccessor(s);
          break;
        case "bufferView":
          n = this._invokeOne(function(o) {
            return o.loadBufferView && o.loadBufferView(s);
          });
          break;
        case "buffer":
          n = this.loadBuffer(s);
          break;
        case "material":
          n = this._invokeOne(function(o) {
            return o.loadMaterial && o.loadMaterial(s);
          });
          break;
        case "texture":
          n = this._invokeOne(function(o) {
            return o.loadTexture && o.loadTexture(s);
          });
          break;
        case "skin":
          n = this.loadSkin(s);
          break;
        case "animation":
          n = this._invokeOne(function(o) {
            return o.loadAnimation && o.loadAnimation(s);
          });
          break;
        case "camera":
          n = this.loadCamera(s);
          break;
        default:
          if (n = this._invokeOne(function(o) {
            return o != this && o.getDependency && o.getDependency(t, s);
          }), !n)
            throw new Error("Unknown type: " + t);
          break;
      }
      this.cache.add(e, n);
    }
    return n;
  }
  /**
   * Requests all dependencies of the specified type asynchronously, with caching.
   * @param {string} type
   * @return {Promise<Array<Object>>}
   */
  getDependencies(t) {
    let s = this.cache.get(t);
    if (!s) {
      const e = this, n = this.json[t + (t === "mesh" ? "es" : "s")] || [];
      s = Promise.all(
        n.map(function(o, r) {
          return e.getDependency(t, r);
        })
      ), this.cache.add(t, s);
    }
    return s;
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/blob/master/specification/2.0/README.md#buffers-and-buffer-views
   * @param {number} bufferIndex
   * @return {Promise<ArrayBuffer>}
   */
  loadBuffer(t) {
    const s = this.json.buffers[t], e = this.fileLoader;
    if (s.type && s.type !== "arraybuffer")
      throw new Error("THREE.GLTFLoader: " + s.type + " buffer type is not supported.");
    if (s.uri === void 0 && t === 0)
      return Promise.resolve(this.extensions[T.KHR_BINARY_GLTF].body);
    const n = this.options;
    return new Promise(function(o, r) {
      e.load(Ae.resolveURL(s.uri, n.path), o, void 0, function() {
        r(new Error('THREE.GLTFLoader: Failed to load buffer "' + s.uri + '".'));
      });
    });
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/blob/master/specification/2.0/README.md#buffers-and-buffer-views
   * @param {number} bufferViewIndex
   * @return {Promise<ArrayBuffer>}
   */
  loadBufferView(t) {
    const s = this.json.bufferViews[t];
    return this.getDependency("buffer", s.buffer).then(function(e) {
      const n = s.byteLength || 0, o = s.byteOffset || 0;
      return e.slice(o, o + n);
    });
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/blob/master/specification/2.0/README.md#accessors
   * @param {number} accessorIndex
   * @return {Promise<BufferAttribute|InterleavedBufferAttribute>}
   */
  loadAccessor(t) {
    const s = this, e = this.json, n = this.json.accessors[t];
    if (n.bufferView === void 0 && n.sparse === void 0) {
      const r = ye[n.type], a = ee[n.componentType], i = n.normalized === !0, A = new a(n.count * r);
      return Promise.resolve(new ce(A, r, i));
    }
    const o = [];
    return n.bufferView !== void 0 ? o.push(this.getDependency("bufferView", n.bufferView)) : o.push(null), n.sparse !== void 0 && (o.push(this.getDependency("bufferView", n.sparse.indices.bufferView)), o.push(this.getDependency("bufferView", n.sparse.values.bufferView))), Promise.all(o).then(function(r) {
      const a = r[0], i = ye[n.type], A = ee[n.componentType], B = A.BYTES_PER_ELEMENT, c = B * i, u = n.byteOffset || 0, C = n.bufferView !== void 0 ? e.bufferViews[n.bufferView].byteStride : void 0, d = n.normalized === !0;
      let p, m;
      if (C && C !== c) {
        const E = Math.floor(u / C), G = "InterleavedBuffer:" + n.bufferView + ":" + n.componentType + ":" + E + ":" + n.count;
        let D = s.cache.get(G);
        D || (p = new A(a, E * C, n.count * C / B), D = new ns(p, C / B), s.cache.add(G, D)), m = new Is(
          D,
          i,
          u % C / B,
          d
        );
      } else
        a === null ? p = new A(n.count * i) : p = new A(a, u, n.count * i), m = new ce(p, i, d);
      if (n.sparse !== void 0) {
        const E = ye.SCALAR, G = ee[n.sparse.indices.componentType], D = n.sparse.indices.byteOffset || 0, g = n.sparse.values.byteOffset || 0, R = new G(
          r[1],
          D,
          n.sparse.count * E
        ), M = new A(r[2], g, n.sparse.count * i);
        a !== null && (m = new ce(
          m.array.slice(),
          m.itemSize,
          m.normalized
        ));
        for (let O = 0, P = R.length; O < P; O++) {
          const L = R[O];
          if (m.setX(L, M[O * i]), i >= 2 && m.setY(L, M[O * i + 1]), i >= 3 && m.setZ(L, M[O * i + 2]), i >= 4 && m.setW(L, M[O * i + 3]), i >= 5)
            throw new Error("THREE.GLTFLoader: Unsupported itemSize in sparse BufferAttribute.");
        }
      }
      return m;
    });
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/tree/master/specification/2.0#textures
   * @param {number} textureIndex
   * @return {Promise<THREE.Texture|null>}
   */
  loadTexture(t) {
    const s = this.json, e = this.options, o = s.textures[t].source, r = s.images[o];
    let a = this.textureLoader;
    if (r.uri) {
      const i = e.manager.getHandler(r.uri);
      i !== null && (a = i);
    }
    return this.loadTextureImage(t, o, a);
  }
  loadTextureImage(t, s, e) {
    const n = this, o = this.json, r = o.textures[t], a = o.images[s], i = (a.uri || a.bufferView) + ":" + r.sampler;
    if (this.textureCache[i])
      return this.textureCache[i];
    const A = this.loadImageSource(s, e).then(function(B) {
      B.flipY = !1, B.name = r.name || a.name || "", B.name === "" && typeof a.uri == "string" && a.uri.startsWith("data:image/") === !1 && (B.name = a.uri);
      const u = (o.samplers || {})[r.sampler] || {};
      return B.magFilter = dt[u.magFilter] || Ft, B.minFilter = dt[u.minFilter] || Mt, B.wrapS = ft[u.wrapS] || Ke, B.wrapT = ft[u.wrapT] || Ke, n.associations.set(B, { textures: t }), B;
    }).catch(function() {
      return null;
    });
    return this.textureCache[i] = A, A;
  }
  loadImageSource(t, s) {
    const e = this, n = this.json, o = this.options;
    if (this.sourceCache[t] !== void 0)
      return this.sourceCache[t].then((c) => c.clone());
    const r = n.images[t], a = self.URL || self.webkitURL;
    let i = r.uri || "", A = !1;
    if (r.bufferView !== void 0)
      i = e.getDependency("bufferView", r.bufferView).then(function(c) {
        A = !0;
        const u = new Blob([c], { type: r.mimeType });
        return i = a.createObjectURL(u), i;
      });
    else if (r.uri === void 0)
      throw new Error("THREE.GLTFLoader: Image " + t + " is missing URI and bufferView");
    const B = Promise.resolve(i).then(function(c) {
      return new Promise(function(u, C) {
        let d = u;
        s.isImageBitmapLoader === !0 && (d = function(p) {
          const m = new at(p);
          m.needsUpdate = !0, u(m);
        }), s.load(Ae.resolveURL(c, o.path), d, void 0, C);
      });
    }).then(function(c) {
      return A === !0 && a.revokeObjectURL(i), v(c, r), c.userData.mimeType = r.mimeType || Mn(r.uri), c;
    }).catch(function(c) {
      throw console.error("THREE.GLTFLoader: Couldn't load texture", i), c;
    });
    return this.sourceCache[t] = B, B;
  }
  /**
   * Asynchronously assigns a texture to the given material parameters.
   * @param {Object} materialParams
   * @param {string} mapName
   * @param {Object} mapDef
   * @return {Promise<Texture>}
   */
  assignTexture(t, s, e, n) {
    const o = this;
    return this.getDependency("texture", e.index).then(function(r) {
      if (!r)
        return null;
      if (e.texCoord !== void 0 && e.texCoord > 0 && (r = r.clone(), r.channel = e.texCoord), o.extensions[T.KHR_TEXTURE_TRANSFORM]) {
        const a = e.extensions !== void 0 ? e.extensions[T.KHR_TEXTURE_TRANSFORM] : void 0;
        if (a) {
          const i = o.associations.get(r);
          r = o.extensions[T.KHR_TEXTURE_TRANSFORM].extendTexture(r, a), o.associations.set(r, i);
        }
      }
      return n !== void 0 && (typeof n == "number" && (n = n === ht ? W : _), "colorSpace" in r ? r.colorSpace = n : r.encoding = n === W ? ht : _s), t[s] = r, r;
    });
  }
  /**
   * Assigns final material to a Mesh, Line, or Points instance. The instance
   * already has a material (generated from the glTF material options alone)
   * but reuse of the same glTF material may require multiple threejs materials
   * to accommodate different primitive types, defines, etc. New materials will
   * be created if necessary, and reused from a cache.
   * @param  {Object3D} mesh Mesh, Line, or Points instance.
   */
  assignFinalMaterial(t) {
    const s = t.geometry;
    let e = t.material;
    const n = s.attributes.tangent === void 0, o = s.attributes.color !== void 0, r = s.attributes.normal === void 0;
    if (t.isPoints) {
      const a = "PointsMaterial:" + e.uuid;
      let i = this.cache.get(a);
      i || (i = new Bs(), Le.prototype.copy.call(i, e), i.color.copy(e.color), i.map = e.map, i.sizeAttenuation = !1, this.cache.add(a, i)), e = i;
    } else if (t.isLine) {
      const a = "LineBasicMaterial:" + e.uuid;
      let i = this.cache.get(a);
      i || (i = new ls(), Le.prototype.copy.call(i, e), i.color.copy(e.color), i.map = e.map, this.cache.add(a, i)), e = i;
    }
    if (n || o || r) {
      let a = "ClonedMaterial:" + e.uuid + ":";
      n && (a += "derivative-tangents:"), o && (a += "vertex-colors:"), r && (a += "flat-shading:");
      let i = this.cache.get(a);
      i || (i = e.clone(), o && (i.vertexColors = !0), r && (i.flatShading = !0), n && (i.normalScale && (i.normalScale.y *= -1), i.clearcoatNormalScale && (i.clearcoatNormalScale.y *= -1)), this.cache.add(a, i), this.associations.set(i, this.associations.get(e))), e = i;
    }
    t.material = e;
  }
  getMaterialType() {
    return Gt;
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/blob/master/specification/2.0/README.md#materials
   * @param {number} materialIndex
   * @return {Promise<Material>}
   */
  loadMaterial(t) {
    const s = this, e = this.json, n = this.extensions, o = e.materials[t];
    let r;
    const a = {}, i = o.extensions || {}, A = [];
    if (i[T.KHR_MATERIALS_UNLIT]) {
      const c = n[T.KHR_MATERIALS_UNLIT];
      r = c.getMaterialType(), A.push(c.extendParams(a, o, s));
    } else {
      const c = o.pbrMetallicRoughness || {};
      if (a.color = new V(1, 1, 1), a.opacity = 1, Array.isArray(c.baseColorFactor)) {
        const u = c.baseColorFactor;
        a.color.setRGB(u[0], u[1], u[2], _), a.opacity = u[3];
      }
      c.baseColorTexture !== void 0 && A.push(s.assignTexture(a, "map", c.baseColorTexture, W)), a.metalness = c.metallicFactor !== void 0 ? c.metallicFactor : 1, a.roughness = c.roughnessFactor !== void 0 ? c.roughnessFactor : 1, c.metallicRoughnessTexture !== void 0 && (A.push(s.assignTexture(a, "metalnessMap", c.metallicRoughnessTexture)), A.push(s.assignTexture(a, "roughnessMap", c.metallicRoughnessTexture))), r = this._invokeOne(function(u) {
        return u.getMaterialType && u.getMaterialType(t);
      }), A.push(
        Promise.all(
          this._invokeAll(function(u) {
            return u.extendMaterialParams && u.extendMaterialParams(t, a);
          })
        )
      );
    }
    o.doubleSided === !0 && (a.side = us);
    const B = o.alphaMode || Oe.OPAQUE;
    if (B === Oe.BLEND ? (a.transparent = !0, a.depthWrite = !1) : (a.transparent = !1, B === Oe.MASK && (a.alphaTest = o.alphaCutoff !== void 0 ? o.alphaCutoff : 0.5)), o.normalTexture !== void 0 && r !== ae && (A.push(s.assignTexture(a, "normalMap", o.normalTexture)), a.normalScale = new S(1, 1), o.normalTexture.scale !== void 0)) {
      const c = o.normalTexture.scale;
      a.normalScale.set(c, c);
    }
    if (o.occlusionTexture !== void 0 && r !== ae && (A.push(s.assignTexture(a, "aoMap", o.occlusionTexture)), o.occlusionTexture.strength !== void 0 && (a.aoMapIntensity = o.occlusionTexture.strength)), o.emissiveFactor !== void 0 && r !== ae) {
      const c = o.emissiveFactor;
      a.emissive = new V().setRGB(
        c[0],
        c[1],
        c[2],
        _
      );
    }
    return o.emissiveTexture !== void 0 && r !== ae && A.push(s.assignTexture(a, "emissiveMap", o.emissiveTexture, W)), Promise.all(A).then(function() {
      const c = new r(a);
      return o.name && (c.name = o.name), v(c, o), s.associations.set(c, { materials: t }), o.extensions && Z(n, c, o), c;
    });
  }
  /** When Object3D instances are targeted by animation, they need unique names. */
  createUniqueName(t) {
    const s = hs.sanitizeNodeName(t || "");
    return s in this.nodeNamesUsed ? s + "_" + ++this.nodeNamesUsed[s] : (this.nodeNamesUsed[s] = 0, s);
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/blob/master/specification/2.0/README.md#geometry
   *
   * Creates BufferGeometries from primitives.
   *
   * @param {Array<GLTF.Primitive>} primitives
   * @return {Promise<Array<BufferGeometry>>}
   */
  loadGeometries(t) {
    const s = this, e = this.extensions, n = this.primitiveCache;
    function o(a) {
      return e[T.KHR_DRACO_MESH_COMPRESSION].decodePrimitive(a, s).then(function(i) {
        return mt(i, a, s);
      });
    }
    const r = [];
    for (let a = 0, i = t.length; a < i; a++) {
      const A = t[a], B = En(A), c = n[B];
      if (c)
        r.push(c.promise);
      else {
        let u;
        A.extensions && A.extensions[T.KHR_DRACO_MESH_COMPRESSION] ? u = o(A) : u = mt(new Dt(), A, s), n[B] = { primitive: A, promise: u }, r.push(u);
      }
    }
    return Promise.all(r);
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/blob/master/specification/2.0/README.md#meshes
   * @param {number} meshIndex
   * @return {Promise<Group|Mesh|SkinnedMesh>}
   */
  loadMesh(t) {
    const s = this, e = this.json, n = this.extensions, o = e.meshes[t], r = o.primitives, a = [];
    for (let i = 0, A = r.length; i < A; i++) {
      const B = r[i].material === void 0 ? fn(this.cache) : this.getDependency("material", r[i].material);
      a.push(B);
    }
    return a.push(s.loadGeometries(r)), Promise.all(a).then(function(i) {
      const A = i.slice(0, i.length - 1), B = i[i.length - 1], c = [];
      for (let C = 0, d = B.length; C < d; C++) {
        const p = B[C], m = r[C];
        let E;
        const G = A[C];
        if (m.mode === x.TRIANGLES || m.mode === x.TRIANGLE_STRIP || m.mode === x.TRIANGLE_FAN || m.mode === void 0)
          E = o.isSkinnedMesh === !0 ? new Cs(p, G) : new ds(p, G), E.isSkinnedMesh === !0 && E.normalizeSkinWeights(), m.mode === x.TRIANGLE_STRIP ? E.geometry = it(E.geometry, Hs) : m.mode === x.TRIANGLE_FAN && (E.geometry = it(E.geometry, Ls));
        else if (m.mode === x.LINES)
          E = new fs(p, G);
        else if (m.mode === x.LINE_STRIP)
          E = new ms(p, G);
        else if (m.mode === x.LINE_LOOP)
          E = new ps(p, G);
        else if (m.mode === x.POINTS)
          E = new Es(p, G);
        else
          throw new Error("THREE.GLTFLoader: Primitive mode unsupported: " + m.mode);
        Object.keys(E.geometry.morphAttributes).length > 0 && pn(E, o), E.name = s.createUniqueName(o.name || "mesh_" + t), v(E, o), m.extensions && Z(n, E, m), s.assignFinalMaterial(E), c.push(E);
      }
      for (let C = 0, d = c.length; C < d; C++)
        s.associations.set(c[C], {
          meshes: t,
          primitives: C
        });
      if (c.length === 1)
        return o.extensions && Z(n, c[0], o), c[0];
      const u = new Je();
      o.extensions && Z(n, u, o), s.associations.set(u, { meshes: t });
      for (let C = 0, d = c.length; C < d; C++)
        u.add(c[C]);
      return u;
    });
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/tree/master/specification/2.0#cameras
   * @param {number} cameraIndex
   * @return {Promise<THREE.Camera>}
   */
  loadCamera(t) {
    let s;
    const e = this.json.cameras[t], n = e[e.type];
    if (!n) {
      console.warn("THREE.GLTFLoader: Missing camera parameters.");
      return;
    }
    return e.type === "perspective" ? s = new me(
      Ms.radToDeg(n.yfov),
      n.aspectRatio || 1,
      n.znear || 1,
      n.zfar || 2e6
    ) : e.type === "orthographic" && (s = new fe(-n.xmag, n.xmag, n.ymag, -n.ymag, n.znear, n.zfar)), e.name && (s.name = this.createUniqueName(e.name)), v(s, e), Promise.resolve(s);
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/tree/master/specification/2.0#skins
   * @param {number} skinIndex
   * @return {Promise<Skeleton>}
   */
  loadSkin(t) {
    const s = this.json.skins[t], e = [];
    for (let n = 0, o = s.joints.length; n < o; n++)
      e.push(this._loadNodeShallow(s.joints[n]));
    return s.inverseBindMatrices !== void 0 ? e.push(this.getDependency("accessor", s.inverseBindMatrices)) : e.push(null), Promise.all(e).then(function(n) {
      const o = n.pop(), r = n, a = [], i = [];
      for (let A = 0, B = r.length; A < B; A++) {
        const c = r[A];
        if (c) {
          a.push(c);
          const u = new Me();
          o !== null && u.fromArray(o.array, A * 16), i.push(u);
        } else
          console.warn('THREE.GLTFLoader: Joint "%s" could not be found.', s.joints[A]);
      }
      return new Fs(a, i);
    });
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/tree/master/specification/2.0#animations
   * @param {number} animationIndex
   * @return {Promise<AnimationClip>}
   */
  loadAnimation(t) {
    const s = this.json, e = this, n = s.animations[t], o = n.name ? n.name : "animation_" + t, r = [], a = [], i = [], A = [], B = [];
    for (let c = 0, u = n.channels.length; c < u; c++) {
      const C = n.channels[c], d = n.samplers[C.sampler], p = C.target, m = p.node, E = n.parameters !== void 0 ? n.parameters[d.input] : d.input, G = n.parameters !== void 0 ? n.parameters[d.output] : d.output;
      p.node !== void 0 && (r.push(this.getDependency("node", m)), a.push(this.getDependency("accessor", E)), i.push(this.getDependency("accessor", G)), A.push(d), B.push(p));
    }
    return Promise.all([
      Promise.all(r),
      Promise.all(a),
      Promise.all(i),
      Promise.all(A),
      Promise.all(B)
    ]).then(function(c) {
      const u = c[0], C = c[1], d = c[2], p = c[3], m = c[4], E = [];
      for (let G = 0, D = u.length; G < D; G++) {
        const g = u[G], R = C[G], M = d[G], O = p[G], P = m[G];
        if (g === void 0)
          continue;
        g.updateMatrix && g.updateMatrix();
        const L = e._createAnimationTracks(g, R, M, O, P);
        if (L)
          for (let b = 0; b < L.length; b++)
            E.push(L[b]);
      }
      return new Gs(o, void 0, E);
    });
  }
  createNodeMesh(t) {
    const s = this.json, e = this, n = s.nodes[t];
    return n.mesh === void 0 ? null : e.getDependency("mesh", n.mesh).then(function(o) {
      const r = e._getNodeRef(e.meshCache, n.mesh, o);
      return n.weights !== void 0 && r.traverse(function(a) {
        if (a.isMesh)
          for (let i = 0, A = n.weights.length; i < A; i++)
            a.morphTargetInfluences[i] = n.weights[i];
      }), r;
    });
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/tree/master/specification/2.0#nodes-and-hierarchy
   * @param {number} nodeIndex
   * @return {Promise<Object3D>}
   */
  loadNode(t) {
    const s = this.json, e = this, n = s.nodes[t], o = e._loadNodeShallow(t), r = [], a = n.children || [];
    for (let A = 0, B = a.length; A < B; A++)
      r.push(e.getDependency("node", a[A]));
    const i = n.skin === void 0 ? Promise.resolve(null) : e.getDependency("skin", n.skin);
    return Promise.all([o, Promise.all(r), i]).then(function(A) {
      const B = A[0], c = A[1], u = A[2];
      u !== null && B.traverse(function(C) {
        C.isSkinnedMesh && C.bind(u, Fn);
      });
      for (let C = 0, d = c.length; C < d; C++)
        B.add(c[C]);
      return B;
    });
  }
  // ._loadNodeShallow() parses a single node.
  // skin and child nodes are created and added in .loadNode() (no '_' prefix).
  _loadNodeShallow(t) {
    const s = this.json, e = this.extensions, n = this;
    if (this.nodeCache[t] !== void 0)
      return this.nodeCache[t];
    const o = s.nodes[t], r = o.name ? n.createUniqueName(o.name) : "", a = [], i = n._invokeOne(function(A) {
      return A.createNodeMesh && A.createNodeMesh(t);
    });
    return i && a.push(i), o.camera !== void 0 && a.push(
      n.getDependency("camera", o.camera).then(function(A) {
        return n._getNodeRef(n.cameraCache, o.camera, A);
      })
    ), n._invokeAll(function(A) {
      return A.createNodeAttachment && A.createNodeAttachment(t);
    }).forEach(function(A) {
      a.push(A);
    }), this.nodeCache[t] = Promise.all(a).then(function(A) {
      let B;
      if (o.isBone === !0 ? B = new Ds() : A.length > 1 ? B = new Je() : A.length === 1 ? B = A[0] : B = new Et(), B !== A[0])
        for (let c = 0, u = A.length; c < u; c++)
          B.add(A[c]);
      if (o.name && (B.userData.name = o.name, B.name = r), v(B, o), o.extensions && Z(e, B, o), o.matrix !== void 0) {
        const c = new Me();
        c.fromArray(o.matrix), B.applyMatrix4(c);
      } else
        o.translation !== void 0 && B.position.fromArray(o.translation), o.rotation !== void 0 && B.quaternion.fromArray(o.rotation), o.scale !== void 0 && B.scale.fromArray(o.scale);
      return n.associations.has(B) || n.associations.set(B, {}), n.associations.get(B).nodes = t, B;
    }), this.nodeCache[t];
  }
  /**
   * Specification: https://github.com/KhronosGroup/glTF/tree/master/specification/2.0#scenes
   * @param {number} sceneIndex
   * @return {Promise<Group>}
   */
  loadScene(t) {
    const s = this.extensions, e = this.json.scenes[t], n = this, o = new Je();
    e.name && (o.name = n.createUniqueName(e.name)), v(o, e), e.extensions && Z(s, o, e);
    const r = e.nodes || [], a = [];
    for (let i = 0, A = r.length; i < A; i++)
      a.push(n.getDependency("node", r[i]));
    return Promise.all(a).then(function(i) {
      for (let B = 0, c = i.length; B < c; B++)
        o.add(i[B]);
      const A = (B) => {
        const c = /* @__PURE__ */ new Map();
        for (const [u, C] of n.associations)
          (u instanceof Le || u instanceof at) && c.set(u, C);
        return B.traverse((u) => {
          const C = n.associations.get(u);
          C != null && c.set(u, C);
        }), c;
      };
      return n.associations = A(o), o;
    });
  }
  _createAnimationTracks(t, s, e, n, o) {
    const r = [], a = t.name ? t.name : t.uuid, i = [];
    j[o.path] === j.weights ? t.traverse(function(u) {
      u.morphTargetInfluences && i.push(u.name ? u.name : u.uuid);
    }) : i.push(a);
    let A;
    switch (j[o.path]) {
      case j.weights:
        A = ct;
        break;
      case j.rotation:
        A = Bt;
        break;
      case j.position:
      case j.scale:
        A = At;
        break;
      default:
        e.itemSize === 1 ? A = ct : A = At;
        break;
    }
    const B = n.interpolation !== void 0 ? dn[n.interpolation] : gt, c = this._getArrayFromAccessor(e);
    for (let u = 0, C = i.length; u < C; u++) {
      const d = new A(
        i[u] + "." + j[o.path],
        s.array,
        c,
        B
      );
      n.interpolation === "CUBICSPLINE" && this._createCubicSplineTrackInterpolant(d), r.push(d);
    }
    return r;
  }
  _getArrayFromAccessor(t) {
    let s = t.array;
    if (t.normalized) {
      const e = Ne(s.constructor), n = new Float32Array(s.length);
      for (let o = 0, r = s.length; o < r; o++)
        n[o] = s[o] * e;
      s = n;
    }
    return s;
  }
  _createCubicSplineTrackInterpolant(t) {
    t.createInterpolant = function(e) {
      const n = this instanceof Bt ? Cn : Tt;
      return new n(this.times, this.values, this.getValueSize() / 3, e);
    }, t.createInterpolant.isInterpolantFactoryMethodGLTFCubicSpline = !0;
  }
}
function Dn(h, t, s) {
  const e = t.attributes, n = new It();
  if (e.POSITION !== void 0) {
    const a = s.json.accessors[e.POSITION], i = a.min, A = a.max;
    if (i !== void 0 && A !== void 0) {
      if (n.set(new J(i[0], i[1], i[2]), new J(A[0], A[1], A[2])), a.normalized) {
        const B = Ne(ee[a.componentType]);
        n.min.multiplyScalar(B), n.max.multiplyScalar(B);
      }
    } else {
      console.warn("THREE.GLTFLoader: Missing min/max properties for accessor POSITION.");
      return;
    }
  } else
    return;
  const o = t.targets;
  if (o !== void 0) {
    const a = new J(), i = new J();
    for (let A = 0, B = o.length; A < B; A++) {
      const c = o[A];
      if (c.POSITION !== void 0) {
        const u = s.json.accessors[c.POSITION], C = u.min, d = u.max;
        if (C !== void 0 && d !== void 0) {
          if (i.setX(Math.max(Math.abs(C[0]), Math.abs(d[0]))), i.setY(Math.max(Math.abs(C[1]), Math.abs(d[1]))), i.setZ(Math.max(Math.abs(C[2]), Math.abs(d[2]))), u.normalized) {
            const p = Ne(ee[u.componentType]);
            i.multiplyScalar(p);
          }
          a.max(i);
        } else
          console.warn("THREE.GLTFLoader: Missing min/max properties for accessor POSITION.");
      }
    }
    n.expandByVector(a);
  }
  h.boundingBox = n;
  const r = new bs();
  n.getCenter(r.center), r.radius = n.min.distanceTo(n.max) / 2, h.boundingSphere = r;
}
function mt(h, t, s) {
  const e = t.attributes, n = [];
  function o(r, a) {
    return s.getDependency("accessor", r).then(function(i) {
      h.setAttribute(a, i);
    });
  }
  for (const r in e) {
    const a = Ue[r] || r.toLowerCase();
    a in h.attributes || n.push(o(e[r], a));
  }
  if (t.indices !== void 0 && !h.index) {
    const r = s.getDependency("accessor", t.indices).then(function(a) {
      h.setIndex(a);
    });
    n.push(r);
  }
  return v(h, t), Dn(h, t, s), Promise.all(n).then(function() {
    return t.targets !== void 0 ? mn(h, t.targets, s) : h;
  });
}
const Se = /* @__PURE__ */ new WeakMap();
class gn extends pt {
  constructor(t) {
    super(t), this.decoderPath = "", this.decoderConfig = {}, this.decoderBinary = null, this.decoderPending = null, this.workerLimit = 4, this.workerPool = [], this.workerNextTaskID = 1, this.workerSourceURL = "", this.defaultAttributeIDs = {
      position: "POSITION",
      normal: "NORMAL",
      color: "COLOR",
      uv: "TEX_COORD"
    }, this.defaultAttributeTypes = {
      position: "Float32Array",
      normal: "Float32Array",
      color: "Float32Array",
      uv: "Float32Array"
    };
  }
  setDecoderPath(t) {
    return this.decoderPath = t, this;
  }
  setDecoderConfig(t) {
    return this.decoderConfig = t, this;
  }
  setWorkerLimit(t) {
    return this.workerLimit = t, this;
  }
  load(t, s, e, n) {
    const o = new Ee(this.manager);
    o.setPath(this.path), o.setResponseType("arraybuffer"), o.setRequestHeader(this.requestHeader), o.setWithCredentials(this.withCredentials), o.load(
      t,
      (r) => {
        const a = {
          attributeIDs: this.defaultAttributeIDs,
          attributeTypes: this.defaultAttributeTypes,
          useUniqueIDs: !1
        };
        this.decodeGeometry(r, a).then(s).catch(n);
      },
      e,
      n
    );
  }
  /** @deprecated Kept for backward-compatibility with previous DRACOLoader versions. */
  decodeDracoFile(t, s, e, n) {
    const o = {
      attributeIDs: e || this.defaultAttributeIDs,
      attributeTypes: n || this.defaultAttributeTypes,
      useUniqueIDs: !!e
    };
    this.decodeGeometry(t, o).then(s);
  }
  decodeGeometry(t, s) {
    for (const i in s.attributeTypes) {
      const A = s.attributeTypes[i];
      A.BYTES_PER_ELEMENT !== void 0 && (s.attributeTypes[i] = A.name);
    }
    const e = JSON.stringify(s);
    if (Se.has(t)) {
      const i = Se.get(t);
      if (i.key === e)
        return i.promise;
      if (t.byteLength === 0)
        throw new Error(
          "THREE.DRACOLoader: Unable to re-decode a buffer with different settings. Buffer has already been transferred."
        );
    }
    let n;
    const o = this.workerNextTaskID++, r = t.byteLength, a = this._getWorker(o, r).then((i) => (n = i, new Promise((A, B) => {
      n._callbacks[o] = { resolve: A, reject: B }, n.postMessage({ type: "decode", id: o, taskConfig: s, buffer: t }, [t]);
    }))).then((i) => this._createGeometry(i.geometry));
    return a.catch(() => !0).then(() => {
      n && o && this._releaseTask(n, o);
    }), Se.set(t, {
      key: e,
      promise: a
    }), a;
  }
  _createGeometry(t) {
    const s = new Dt();
    t.index && s.setIndex(new ce(t.index.array, 1));
    for (let e = 0; e < t.attributes.length; e++) {
      const n = t.attributes[e], o = n.name, r = n.array, a = n.itemSize;
      s.setAttribute(o, new ce(r, a));
    }
    return s;
  }
  _loadLibrary(t, s) {
    const e = new Ee(this.manager);
    return e.setPath(this.decoderPath), e.setResponseType(s), e.setWithCredentials(this.withCredentials), new Promise((n, o) => {
      e.load(t, n, void 0, o);
    });
  }
  preload() {
    return this._initDecoder(), this;
  }
  _initDecoder() {
    if (this.decoderPending)
      return this.decoderPending;
    const t = typeof WebAssembly != "object" || this.decoderConfig.type === "js", s = [];
    return t ? s.push(this._loadLibrary("draco_decoder.js", "text")) : (s.push(this._loadLibrary("draco_wasm_wrapper.js", "text")), s.push(this._loadLibrary("draco_decoder.wasm", "arraybuffer"))), this.decoderPending = Promise.all(s).then((e) => {
      const n = e[0];
      t || (this.decoderConfig.wasmBinary = e[1]);
      const o = In.toString(), r = [
        "/* draco decoder */",
        n,
        "",
        "/* worker */",
        o.substring(o.indexOf("{") + 1, o.lastIndexOf("}"))
      ].join(`
`);
      this.workerSourceURL = URL.createObjectURL(new Blob([r]));
    }), this.decoderPending;
  }
  _getWorker(t, s) {
    return this._initDecoder().then(() => {
      if (this.workerPool.length < this.workerLimit) {
        const n = new Worker(this.workerSourceURL);
        n._callbacks = {}, n._taskCosts = {}, n._taskLoad = 0, n.postMessage({ type: "init", decoderConfig: this.decoderConfig }), n.onmessage = function(o) {
          const r = o.data;
          switch (r.type) {
            case "decode":
              n._callbacks[r.id].resolve(r);
              break;
            case "error":
              n._callbacks[r.id].reject(r);
              break;
            default:
              console.error('THREE.DRACOLoader: Unexpected message, "' + r.type + '"');
          }
        }, this.workerPool.push(n);
      } else
        this.workerPool.sort(function(n, o) {
          return n._taskLoad > o._taskLoad ? -1 : 1;
        });
      const e = this.workerPool[this.workerPool.length - 1];
      return e._taskCosts[t] = s, e._taskLoad += s, e;
    });
  }
  _releaseTask(t, s) {
    t._taskLoad -= t._taskCosts[s], delete t._callbacks[s], delete t._taskCosts[s];
  }
  debug() {
    console.log(
      "Task load: ",
      this.workerPool.map((t) => t._taskLoad)
    );
  }
  dispose() {
    for (let t = 0; t < this.workerPool.length; ++t)
      this.workerPool[t].terminate();
    return this.workerPool.length = 0, this;
  }
}
function In() {
  let h, t;
  onmessage = function(r) {
    const a = r.data;
    switch (a.type) {
      case "init":
        h = a.decoderConfig, t = new Promise(function(B) {
          h.onModuleLoaded = function(c) {
            B({ draco: c });
          }, DracoDecoderModule(h);
        });
        break;
      case "decode":
        const i = a.buffer, A = a.taskConfig;
        t.then((B) => {
          const c = B.draco, u = new c.Decoder(), C = new c.DecoderBuffer();
          C.Init(new Int8Array(i), i.byteLength);
          try {
            const d = s(c, u, C, A), p = d.attributes.map((m) => m.array.buffer);
            d.index && p.push(d.index.array.buffer), self.postMessage({ type: "decode", id: a.id, geometry: d }, p);
          } catch (d) {
            console.error(d), self.postMessage({ type: "error", id: a.id, error: d.message });
          } finally {
            c.destroy(C), c.destroy(u);
          }
        });
        break;
    }
  };
  function s(r, a, i, A) {
    const B = A.attributeIDs, c = A.attributeTypes;
    let u, C;
    const d = a.GetEncodedGeometryType(i);
    if (d === r.TRIANGULAR_MESH)
      u = new r.Mesh(), C = a.DecodeBufferToMesh(i, u);
    else if (d === r.POINT_CLOUD)
      u = new r.PointCloud(), C = a.DecodeBufferToPointCloud(i, u);
    else
      throw new Error("THREE.DRACOLoader: Unexpected geometry type.");
    if (!C.ok() || u.ptr === 0)
      throw new Error("THREE.DRACOLoader: Decoding failed: " + C.error_msg());
    const p = { index: null, attributes: [] };
    for (const m in B) {
      const E = self[c[m]];
      let G, D;
      if (A.useUniqueIDs)
        D = B[m], G = a.GetAttributeByUniqueId(u, D);
      else {
        if (D = a.GetAttributeId(u, r[B[m]]), D === -1)
          continue;
        G = a.GetAttribute(u, D);
      }
      p.attributes.push(n(r, a, u, m, E, G));
    }
    return d === r.TRIANGULAR_MESH && (p.index = e(r, a, u)), r.destroy(u), p;
  }
  function e(r, a, i) {
    const B = i.num_faces() * 3, c = B * 4, u = r._malloc(c);
    a.GetTrianglesUInt32Array(i, c, u);
    const C = new Uint32Array(r.HEAPF32.buffer, u, B).slice();
    return r._free(u), { array: C, itemSize: 1 };
  }
  function n(r, a, i, A, B, c) {
    const u = c.num_components(), d = i.num_points() * u, p = d * B.BYTES_PER_ELEMENT, m = o(r, B), E = r._malloc(p);
    a.GetAttributeDataArrayForAllPoints(i, c, m, p, E);
    const G = new B(r.HEAPF32.buffer, E, d).slice();
    return r._free(E), {
      name: A,
      array: G,
      itemSize: u
    };
  }
  function o(r, a) {
    switch (a) {
      case Float32Array:
        return r.DT_FLOAT32;
      case Int8Array:
        return r.DT_INT8;
      case Int16Array:
        return r.DT_INT16;
      case Int32Array:
        return r.DT_INT32;
      case Uint8Array:
        return r.DT_UINT8;
      case Uint16Array:
        return r.DT_UINT16;
      case Uint32Array:
        return r.DT_UINT32;
    }
  }
}
let Ce;
const xe = () => {
  if (Ce)
    return Ce;
  const h = "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", t = "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", s = new Uint8Array([
    0,
    97,
    115,
    109,
    1,
    0,
    0,
    0,
    1,
    4,
    1,
    96,
    0,
    0,
    3,
    3,
    2,
    0,
    0,
    5,
    3,
    1,
    0,
    1,
    12,
    1,
    0,
    10,
    22,
    2,
    12,
    0,
    65,
    0,
    65,
    0,
    65,
    0,
    252,
    10,
    0,
    0,
    11,
    7,
    0,
    65,
    0,
    253,
    15,
    26,
    11
  ]), e = new Uint8Array([
    32,
    0,
    65,
    253,
    3,
    1,
    2,
    34,
    4,
    106,
    6,
    5,
    11,
    8,
    7,
    20,
    13,
    33,
    12,
    16,
    128,
    9,
    116,
    64,
    19,
    113,
    127,
    15,
    10,
    21,
    22,
    14,
    255,
    66,
    24,
    54,
    136,
    107,
    18,
    23,
    192,
    26,
    114,
    118,
    132,
    17,
    77,
    101,
    130,
    144,
    27,
    87,
    131,
    44,
    45,
    74,
    156,
    154,
    70,
    167
  ]);
  if (typeof WebAssembly != "object")
    return {
      supported: !1
    };
  let n = h;
  WebAssembly.validate(s) && (n = t);
  let o;
  const r = WebAssembly.instantiate(a(n), {}).then((c) => {
    o = c.instance, o.exports.__wasm_call_ctors();
  });
  function a(c) {
    const u = new Uint8Array(c.length);
    for (let d = 0; d < c.length; ++d) {
      const p = c.charCodeAt(d);
      u[d] = p > 96 ? p - 71 : p > 64 ? p - 65 : p > 47 ? p + 4 : p > 46 ? 63 : 62;
    }
    let C = 0;
    for (let d = 0; d < c.length; ++d)
      u[C++] = u[d] < 60 ? e[u[d]] : (u[d] - 60) * 64 + u[++d];
    return u.buffer.slice(0, C);
  }
  function i(c, u, C, d, p, m) {
    const E = o.exports.sbrk, G = C + 3 & -4, D = E(G * d), g = E(p.length), R = new Uint8Array(o.exports.memory.buffer);
    R.set(p, g);
    const M = c(D, C, d, g, p.length);
    if (M === 0 && m && m(D, G, d), u.set(R.subarray(D, D + C * d)), E(D - E(0)), M !== 0)
      throw new Error(`Malformed buffer data: ${M}`);
  }
  const A = {
    // legacy index-based enums for glTF
    0: "",
    1: "meshopt_decodeFilterOct",
    2: "meshopt_decodeFilterQuat",
    3: "meshopt_decodeFilterExp",
    // string-based enums for glTF
    NONE: "",
    OCTAHEDRAL: "meshopt_decodeFilterOct",
    QUATERNION: "meshopt_decodeFilterQuat",
    EXPONENTIAL: "meshopt_decodeFilterExp"
  }, B = {
    // legacy index-based enums for glTF
    0: "meshopt_decodeVertexBuffer",
    1: "meshopt_decodeIndexBuffer",
    2: "meshopt_decodeIndexSequence",
    // string-based enums for glTF
    ATTRIBUTES: "meshopt_decodeVertexBuffer",
    TRIANGLES: "meshopt_decodeIndexBuffer",
    INDICES: "meshopt_decodeIndexSequence"
  };
  return Ce = {
    ready: r,
    supported: !0,
    decodeVertexBuffer(c, u, C, d, p) {
      i(
        o.exports.meshopt_decodeVertexBuffer,
        c,
        u,
        C,
        d,
        o.exports[A[p]]
      );
    },
    decodeIndexBuffer(c, u, C, d) {
      i(o.exports.meshopt_decodeIndexBuffer, c, u, C, d);
    },
    decodeIndexSequence(c, u, C, d) {
      i(o.exports.meshopt_decodeIndexSequence, c, u, C, d);
    },
    decodeGltfBuffer(c, u, C, d, p, m) {
      i(
        o.exports[B[p]],
        c,
        u,
        C,
        d,
        o.exports[A[m]]
      );
    }
  }, Ce;
};
let de = null, bt = "https://www.gstatic.com/draco/versioned/decoders/1.5.5/";
function Ht(h = !0, t = !0, s) {
  return (e) => {
    s && s(e), h && (de || (de = new gn()), de.setDecoderPath(typeof h == "string" ? h : bt), e.setDRACOLoader(de)), t && e.setMeshoptDecoder(typeof xe == "function" ? xe() : xe);
  };
}
const Ge = (h, t, s, e) => we(ve, h, Ht(t, s, e));
Ge.preload = (h, t, s, e) => we.preload(ve, h, Ht(t, s, e));
Ge.clear = (h) => we.clear(ve, h);
Ge.setDecoderPath = (h) => {
  bt = h;
};
const Rn = /* @__PURE__ */ X.forwardRef(({
  makeDefault: h,
  camera: t,
  regress: s,
  domElement: e,
  enableDamping: n = !0,
  keyEvents: o = !1,
  onChange: r,
  onStart: a,
  onEnd: i,
  ...A
}, B) => {
  const c = k((M) => M.invalidate), u = k((M) => M.camera), C = k((M) => M.gl), d = k((M) => M.events), p = k((M) => M.setEvents), m = k((M) => M.set), E = k((M) => M.get), G = k((M) => M.performance), D = t || u, g = e || d.connected || C.domElement, R = X.useMemo(() => new vs(D), [D]);
  return Js(() => {
    R.enabled && R.update();
  }, -1), X.useEffect(() => (o && R.connect(o === !0 ? g : o), R.connect(g), () => {
    R.dispose();
  }), [o, g, s, R, c]), X.useEffect(() => {
    const M = (L) => {
      c(), s && G.regress(), r && r(L);
    }, O = (L) => {
      a && a(L);
    }, P = (L) => {
      i && i(L);
    };
    return R.addEventListener("change", M), R.addEventListener("start", O), R.addEventListener("end", P), () => {
      R.removeEventListener("start", O), R.removeEventListener("end", P), R.removeEventListener("change", M);
    };
  }, [r, a, i, R, c, p]), X.useEffect(() => {
    if (h) {
      const M = E().controls;
      return m({
        controls: R
      }), () => m({
        controls: M
      });
    }
  }, [h, R]), /* @__PURE__ */ X.createElement("primitive", ys({
    ref: B,
    object: R,
    enableDamping: n
  }, A));
});
function Jn({ modelUrl: h, paint: t, view: s, motionAllowed: e, onReady: n }) {
  const { scene: o } = Ge(h, !1, !0), { model: r, scale: a, center: i, floor: A } = X.useMemo(() => {
    const c = o.clone(!0), u = new It().setFromObject(c), C = u.getSize(new J());
    if (!Number.isFinite(C.x) || C.length() < 0.01)
      throw new Error("Invalid licensed showroom GLB geometry");
    const p = 4.65 / Math.max(C.x, C.z);
    return c.traverse((m) => {
      if (!m.isMesh) return;
      m.castShadow = !1, m.receiveShadow = !1;
      const G = (Array.isArray(m.material) ? m.material : [m.material]).map((D) => {
        if (!D) return D;
        const g = /^Paint [12] Carmine$/.test(D.name || ""), R = !!D.isMeshPhysicalMaterial && (D.transmission > 0 || D.iridescence > 0);
        if (!g && !R) return D;
        const M = D.clone();
        return M.userData.empireStudioDerived = !0, g && (M.color.set(t.body), M.metalness = Math.max(M.metalness ?? 0.5, 0.66), M.roughness = 0.24), "transmission" in M && (M.transmission = 0), "iridescence" in M && (M.iridescence = 0), "clearcoat" in M && (M.clearcoat = 0.6, M.clearcoatRoughness = 0.12), M;
      });
      m.material = Array.isArray(m.material) ? G : G[0];
    }), {
      model: c,
      scale: p,
      center: u.getCenter(new J()),
      floor: u.min.y
    };
  }, [o, t.body]);
  X.useEffect(() => (n?.(), () => {
    r.traverse((c) => {
      if (!c.isMesh) return;
      (Array.isArray(c.material) ? c.material : [c.material]).forEach((C) => {
        C && C.userData?.empireStudioDerived === !0 && C.dispose();
      });
    });
  }), [r, n, o]);
  const B = s === "front" ? 0.7 : s === "side" ? -0.85 : 0.1;
  return /* @__PURE__ */ re.jsxs(re.Fragment, { children: [
    /* @__PURE__ */ re.jsx("group", { position: [0, -0.64, 0], rotation: [0, B, 0], children: /* @__PURE__ */ re.jsx(
      "primitive",
      {
        object: r,
        scale: a,
        position: [-i.x * a, -A * a, -i.z * a]
      }
    ) }),
    /* @__PURE__ */ re.jsx(
      Rn,
      {
        makeDefault: !0,
        enableDamping: !1,
        enablePan: !1,
        enableZoom: !0,
        minDistance: 5.4,
        maxDistance: 12,
        minPolarAngle: 0.6,
        maxPolarAngle: 1.75,
        target: [0, 0.18, 0]
      }
    )
  ] });
}
export {
  Jn as default
};
