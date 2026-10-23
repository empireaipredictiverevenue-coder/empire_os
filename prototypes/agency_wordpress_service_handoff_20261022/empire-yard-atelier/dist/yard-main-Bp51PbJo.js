function nT(i) {
  return i && i.__esModule && Object.prototype.hasOwnProperty.call(i, "default") ? i.default : i;
}
var Pc = { exports: {} }, Kl = {};
var Zp;
function aT() {
  if (Zp) return Kl;
  Zp = 1;
  var i = /* @__PURE__ */ Symbol.for("react.transitional.element"), l = /* @__PURE__ */ Symbol.for("react.fragment");
  function r(o, c, d) {
    var h = null;
    if (d !== void 0 && (h = "" + d), c.key !== void 0 && (h = "" + c.key), "key" in c) {
      d = {};
      for (var y in c)
        y !== "key" && (d[y] = c[y]);
    } else d = c;
    return c = d.ref, {
      $$typeof: i,
      type: o,
      key: h,
      ref: c !== void 0 ? c : null,
      props: d
    };
  }
  return Kl.Fragment = l, Kl.jsx = r, Kl.jsxs = r, Kl;
}
var Kp;
function iT() {
  return Kp || (Kp = 1, Pc.exports = aT()), Pc.exports;
}
var R = iT(), Fc = { exports: {} }, st = {};
var Jp;
function lT() {
  if (Jp) return st;
  Jp = 1;
  var i = /* @__PURE__ */ Symbol.for("react.transitional.element"), l = /* @__PURE__ */ Symbol.for("react.portal"), r = /* @__PURE__ */ Symbol.for("react.fragment"), o = /* @__PURE__ */ Symbol.for("react.strict_mode"), c = /* @__PURE__ */ Symbol.for("react.profiler"), d = /* @__PURE__ */ Symbol.for("react.consumer"), h = /* @__PURE__ */ Symbol.for("react.context"), y = /* @__PURE__ */ Symbol.for("react.forward_ref"), v = /* @__PURE__ */ Symbol.for("react.suspense"), b = /* @__PURE__ */ Symbol.for("react.memo"), g = /* @__PURE__ */ Symbol.for("react.lazy"), p = /* @__PURE__ */ Symbol.for("react.activity"), T = /* @__PURE__ */ Symbol.for("react.view_transition"), V = Symbol.iterator;
  function z(E) {
    return E === null || typeof E != "object" ? null : (E = V && E[V] || E["@@iterator"], typeof E == "function" ? E : null);
  }
  var B = {
    isMounted: function() {
      return !1;
    },
    enqueueForceUpdate: function() {
    },
    enqueueReplaceState: function() {
    },
    enqueueSetState: function() {
    }
  }, j = Object.assign, L = {};
  function Y(E, H, tt) {
    this.props = E, this.context = H, this.refs = L, this.updater = tt || B;
  }
  Y.prototype.isReactComponent = {}, Y.prototype.setState = function(E, H) {
    if (typeof E != "object" && typeof E != "function" && E != null)
      throw Error(
        "takes an object of state variables to update or a function which returns an object of state variables."
      );
    this.updater.enqueueSetState(this, E, H, "setState");
  }, Y.prototype.forceUpdate = function(E) {
    this.updater.enqueueForceUpdate(this, E, "forceUpdate");
  };
  function U() {
  }
  U.prototype = Y.prototype;
  function G(E, H, tt) {
    this.props = E, this.context = H, this.refs = L, this.updater = tt || B;
  }
  var nt = G.prototype = new U();
  nt.constructor = G, j(nt, Y.prototype), nt.isPureReactComponent = !0;
  var rt = Array.isArray;
  function J() {
  }
  var Q = { H: null, A: null, T: null, S: null }, Ot = Object.prototype.hasOwnProperty;
  function $(E, H, tt) {
    var et = tt.ref;
    return {
      $$typeof: i,
      type: E,
      key: H,
      ref: et !== void 0 ? et : null,
      props: tt
    };
  }
  function vt(E, H) {
    return $(E.type, H, E.props);
  }
  function Nt(E) {
    return typeof E == "object" && E !== null && E.$$typeof === i;
  }
  function de(E) {
    var H = { "=": "=0", ":": "=2" };
    return "$" + E.replace(/[=:]/g, function(tt) {
      return H[tt];
    });
  }
  var Wt = /\/+/g;
  function zt(E, H) {
    return typeof E == "object" && E !== null && E.key != null ? de("" + E.key) : H.toString(36);
  }
  function q(E) {
    switch (E.status) {
      case "fulfilled":
        return E.value;
      case "rejected":
        throw E.reason;
      default:
        switch (typeof E.status == "string" ? E.then(J, J) : (E.status = "pending", E.then(
          function(H) {
            E.status === "pending" && (E.status = "fulfilled", E.value = H);
          },
          function(H) {
            E.status === "pending" && (E.status = "rejected", E.reason = H);
          }
        )), E.status) {
          case "fulfilled":
            return E.value;
          case "rejected":
            throw E.reason;
        }
    }
    throw E;
  }
  function it(E, H, tt, et, bt) {
    var St = typeof E;
    (St === "undefined" || St === "boolean") && (E = null);
    var xt = !1;
    if (E === null) xt = !0;
    else
      switch (St) {
        case "bigint":
        case "string":
        case "number":
          xt = !0;
          break;
        case "object":
          switch (E.$$typeof) {
            case i:
            case l:
              xt = !0;
              break;
            case g:
              return xt = E._init, it(
                xt(E._payload),
                H,
                tt,
                et,
                bt
              );
          }
      }
    if (xt)
      return bt = bt(E), xt = et === "" ? "." + zt(E, 0) : et, rt(bt) ? (tt = "", xt != null && (tt = xt.replace(Wt, "$&/") + "/"), it(bt, H, tt, "", function(An) {
        return An;
      })) : bt != null && (Nt(bt) && (bt = vt(
        bt,
        tt + (bt.key == null || E && E.key === bt.key ? "" : ("" + bt.key).replace(
          Wt,
          "$&/"
        ) + "/") + xt
      )), H.push(bt)), 1;
    xt = 0;
    var W = et === "" ? "." : et + ":";
    if (rt(E))
      for (var lt = 0; lt < E.length; lt++)
        et = E[lt], St = W + zt(et, lt), xt += it(
          et,
          H,
          tt,
          St,
          bt
        );
    else if (lt = z(E), typeof lt == "function")
      for (E = lt.call(E), lt = 0; !(et = E.next()).done; )
        et = et.value, St = W + zt(et, lt++), xt += it(
          et,
          H,
          tt,
          St,
          bt
        );
    else if (St === "object") {
      if (typeof E.then == "function")
        return it(
          q(E),
          H,
          tt,
          et,
          bt
        );
      throw H = String(E), Error(
        "Objects are not valid as a React child (found: " + (H === "[object Object]" ? "object with keys {" + Object.keys(E).join(", ") + "}" : H) + "). If you meant to render a collection of children, use an array instead."
      );
    }
    return xt;
  }
  function k(E, H, tt) {
    if (E == null) return E;
    var et = [], bt = 0;
    return it(E, et, "", "", function(St) {
      return H.call(tt, St, bt++);
    }), et;
  }
  function ct(E) {
    if (E._status === -1) {
      var H = E._result, tt = H();
      tt.then(
        function(et) {
          (E._status === 0 || E._status === -1) && (E._status = 1, E._result = et, tt.status === void 0 && (tt.status = "fulfilled", tt.value = et));
        },
        function(et) {
          (E._status === 0 || E._status === -1) && (E._status = 2, E._result = et, tt.status === void 0 && (tt.status = "rejected", tt.reason = et));
        }
      ), E._status === -1 && (E._status = 0, E._result = tt);
    }
    if (E._status === 1) return E._result.default;
    throw E._result;
  }
  var ht = typeof reportError == "function" ? reportError : function(E) {
    if (typeof window == "object" && typeof window.ErrorEvent == "function") {
      var H = new window.ErrorEvent("error", {
        bubbles: !0,
        cancelable: !0,
        message: typeof E == "object" && E !== null && typeof E.message == "string" ? String(E.message) : String(E),
        error: E
      });
      if (!window.dispatchEvent(H)) return;
    } else if (typeof process == "object" && typeof process.emit == "function") {
      process.emit("uncaughtException", E);
      return;
    }
    console.error(E);
  };
  function It(E) {
    var H = Q.T, tt = {};
    tt.types = H !== null ? H.types : null, Q.T = tt;
    try {
      var et = E(), bt = Q.S;
      bt !== null && bt(tt, et), typeof et == "object" && et !== null && typeof et.then == "function" && et.then(J, ht);
    } catch (St) {
      ht(St);
    } finally {
      H !== null && tt.types !== null && (H.types = tt.types), Q.T = H;
    }
  }
  function Fe(E) {
    var H = Q.T;
    if (H !== null) {
      var tt = H.types;
      tt === null ? H.types = [E] : tt.indexOf(E) === -1 && tt.push(E);
    } else It(Fe.bind(null, E));
  }
  var Ta = {
    map: k,
    forEach: function(E, H, tt) {
      k(
        E,
        function() {
          H.apply(this, arguments);
        },
        tt
      );
    },
    count: function(E) {
      var H = 0;
      return k(E, function() {
        H++;
      }), H;
    },
    toArray: function(E) {
      return k(E, function(H) {
        return H;
      }) || [];
    },
    only: function(E) {
      if (!Nt(E))
        throw Error(
          "React.Children.only expected to receive a single React element child."
        );
      return E;
    }
  };
  return st.Activity = p, st.Children = Ta, st.Component = Y, st.Fragment = r, st.Profiler = c, st.PureComponent = G, st.StrictMode = o, st.Suspense = v, st.ViewTransition = T, st.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE = Q, st.__COMPILER_RUNTIME = {
    __proto__: null,
    c: function(E) {
      return Q.H.useMemoCache(E);
    }
  }, st.addTransitionType = Fe, st.cache = function(E) {
    return function() {
      return E.apply(null, arguments);
    };
  }, st.cacheSignal = function() {
    return null;
  }, st.cloneElement = function(E, H, tt) {
    if (E == null)
      throw Error(
        "The argument must be a React element, but you passed " + E + "."
      );
    var et = j({}, E.props), bt = E.key;
    if (H != null)
      for (St in H.key !== void 0 && (bt = "" + H.key), H)
        !Ot.call(H, St) || St === "key" || St === "__self" || St === "__source" || St === "ref" && H.ref === void 0 || (et[St] = H[St]);
    var St = arguments.length - 2;
    if (St === 1) et.children = tt;
    else if (1 < St) {
      for (var xt = Array(St), W = 0; W < St; W++)
        xt[W] = arguments[W + 2];
      et.children = xt;
    }
    return $(E.type, bt, et);
  }, st.createContext = function(E) {
    return E = {
      $$typeof: h,
      _currentValue: E,
      _currentValue2: E,
      _threadCount: 0,
      Provider: null,
      Consumer: null
    }, E.Provider = E, E.Consumer = {
      $$typeof: d,
      _context: E
    }, E;
  }, st.createElement = function(E, H, tt) {
    var et, bt = {}, St = null;
    if (H != null)
      for (et in H.key !== void 0 && (St = "" + H.key), H)
        Ot.call(H, et) && et !== "key" && et !== "__self" && et !== "__source" && (bt[et] = H[et]);
    var xt = arguments.length - 2;
    if (xt === 1) bt.children = tt;
    else if (1 < xt) {
      for (var W = Array(xt), lt = 0; lt < xt; lt++)
        W[lt] = arguments[lt + 2];
      bt.children = W;
    }
    if (E && E.defaultProps)
      for (et in xt = E.defaultProps, xt)
        bt[et] === void 0 && (bt[et] = xt[et]);
    return $(E, St, bt);
  }, st.createRef = function() {
    return { current: null };
  }, st.forwardRef = function(E) {
    return { $$typeof: y, render: E };
  }, st.isValidElement = Nt, st.lazy = function(E) {
    return {
      $$typeof: g,
      _payload: { _status: -1, _result: E },
      _init: ct
    };
  }, st.memo = function(E, H) {
    return {
      $$typeof: b,
      type: E,
      compare: H === void 0 ? null : H
    };
  }, st.startTransition = It, st.unstable_useCacheRefresh = function() {
    return Q.H.useCacheRefresh();
  }, st.use = function(E) {
    return Q.H.use(E);
  }, st.useActionState = function(E, H, tt) {
    return Q.H.useActionState(E, H, tt);
  }, st.useCallback = function(E, H) {
    return Q.H.useCallback(E, H);
  }, st.useContext = function(E) {
    return Q.H.useContext(E);
  }, st.useDebugValue = function() {
  }, st.useDeferredValue = function(E, H) {
    return Q.H.useDeferredValue(E, H);
  }, st.useEffect = function(E, H) {
    return Q.H.useEffect(E, H);
  }, st.useEffectEvent = function(E) {
    return Q.H.useEffectEvent(E);
  }, st.useId = function() {
    return Q.H.useId();
  }, st.useImperativeHandle = function(E, H, tt) {
    return Q.H.useImperativeHandle(E, H, tt);
  }, st.useInsertionEffect = function(E, H) {
    return Q.H.useInsertionEffect(E, H);
  }, st.useLayoutEffect = function(E, H) {
    return Q.H.useLayoutEffect(E, H);
  }, st.useMemo = function(E, H) {
    return Q.H.useMemo(E, H);
  }, st.useOptimistic = function(E, H) {
    return Q.H.useOptimistic(E, H);
  }, st.useReducer = function(E, H, tt) {
    return Q.H.useReducer(E, H, tt);
  }, st.useRef = function(E) {
    return Q.H.useRef(E);
  }, st.useState = function(E) {
    return Q.H.useState(E);
  }, st.useSyncExternalStore = function(E, H, tt) {
    return Q.H.useSyncExternalStore(
      E,
      H,
      tt
    );
  }, st.useTransition = function() {
    return Q.H.useTransition();
  }, st.version = "19.3.1", st;
}
var kp;
function Jf() {
  return kp || (kp = 1, Fc.exports = lT()), Fc.exports;
}
var K = Jf();
const sT = /* @__PURE__ */ nT(K);
var Wc = { exports: {} }, Jl = {}, Ic = { exports: {} }, $c = {};
var Pp;
function uT() {
  return Pp || (Pp = 1, (function(i) {
    function l(q, it) {
      var k = q.length;
      q.push(it);
      t: for (; 0 < k; ) {
        var ct = k - 1 >>> 1, ht = q[ct];
        if (0 < c(ht, it))
          q[ct] = it, q[k] = ht, k = ct;
        else break t;
      }
    }
    function r(q) {
      return q.length === 0 ? null : q[0];
    }
    function o(q) {
      if (q.length === 0) return null;
      var it = q[0], k = q.pop();
      if (k !== it) {
        q[0] = k;
        t: for (var ct = 0, ht = q.length, It = ht >>> 1; ct < It; ) {
          var Fe = 2 * (ct + 1) - 1, Ta = q[Fe], E = Fe + 1, H = q[E];
          if (0 > c(Ta, k))
            E < ht && 0 > c(H, Ta) ? (q[ct] = H, q[E] = k, ct = E) : (q[ct] = Ta, q[Fe] = k, ct = Fe);
          else if (E < ht && 0 > c(H, k))
            q[ct] = H, q[E] = k, ct = E;
          else break t;
        }
      }
      return it;
    }
    function c(q, it) {
      var k = q.sortIndex - it.sortIndex;
      return k !== 0 ? k : q.id - it.id;
    }
    if (i.unstable_now = void 0, typeof performance == "object" && typeof performance.now == "function") {
      var d = performance;
      i.unstable_now = function() {
        return d.now();
      };
    } else {
      var h = Date, y = h.now();
      i.unstable_now = function() {
        return h.now() - y;
      };
    }
    var v = [], b = [], g = 1, p = null, T = 3, V = !1, z = !1, B = !1, j = !1, L = typeof setTimeout == "function" ? setTimeout : null, Y = typeof clearTimeout == "function" ? clearTimeout : null, U = typeof setImmediate < "u" ? setImmediate : null;
    function G(q) {
      for (var it = r(b); it !== null; ) {
        if (it.callback === null) o(b);
        else if (it.startTime <= q)
          o(b), it.sortIndex = it.expirationTime, l(v, it);
        else break;
        it = r(b);
      }
    }
    function nt(q) {
      if (B = !1, G(q), !z)
        if (r(v) !== null)
          z = !0, rt || (rt = !0, Nt());
        else {
          var it = r(b);
          it !== null && zt(nt, it.startTime - q);
        }
    }
    var rt = !1, J = -1, Q = 5, Ot = -1;
    function $() {
      return j ? !0 : !(i.unstable_now() - Ot < Q);
    }
    function vt() {
      if (j = !1, rt) {
        var q = i.unstable_now();
        Ot = q;
        var it = !0;
        try {
          t: {
            z = !1, B && (B = !1, Y(J), J = -1), V = !0;
            var k = T;
            try {
              e: {
                for (G(q), p = r(v); p !== null && !(p.expirationTime > q && $()); ) {
                  var ct = p.callback;
                  if (typeof ct == "function") {
                    p.callback = null, T = p.priorityLevel;
                    var ht = ct(
                      p.expirationTime <= q
                    );
                    if (q = i.unstable_now(), typeof ht == "function") {
                      p.callback = ht, G(q), it = !0;
                      break e;
                    }
                    p === r(v) && o(v), G(q);
                  } else o(v);
                  p = r(v);
                }
                if (p !== null) it = !0;
                else {
                  var It = r(b);
                  It !== null && zt(
                    nt,
                    It.startTime - q
                  ), it = !1;
                }
              }
              break t;
            } finally {
              p = null, T = k, V = !1;
            }
            it = void 0;
          }
        } finally {
          it ? Nt() : rt = !1;
        }
      }
    }
    var Nt;
    if (typeof U == "function")
      Nt = function() {
        U(vt);
      };
    else if (typeof MessageChannel < "u") {
      var de = new MessageChannel(), Wt = de.port2;
      de.port1.onmessage = vt, Nt = function() {
        Wt.postMessage(null);
      };
    } else
      Nt = function() {
        L(vt, 0);
      };
    function zt(q, it) {
      J = L(function() {
        q(i.unstable_now());
      }, it);
    }
    i.unstable_IdlePriority = 5, i.unstable_ImmediatePriority = 1, i.unstable_LowPriority = 4, i.unstable_NormalPriority = 3, i.unstable_Profiling = null, i.unstable_UserBlockingPriority = 2, i.unstable_cancelCallback = function(q) {
      q.callback = null;
    }, i.unstable_forceFrameRate = function(q) {
      0 > q || 125 < q ? console.error(
        "forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported"
      ) : Q = 0 < q ? Math.floor(1e3 / q) : 5;
    }, i.unstable_getCurrentPriorityLevel = function() {
      return T;
    }, i.unstable_next = function(q) {
      switch (T) {
        case 1:
        case 2:
        case 3:
          var it = 3;
          break;
        default:
          it = T;
      }
      var k = T;
      T = it;
      try {
        return q();
      } finally {
        T = k;
      }
    }, i.unstable_requestPaint = function() {
      j = !0;
    }, i.unstable_runWithPriority = function(q, it) {
      switch (q) {
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
          break;
        default:
          q = 3;
      }
      var k = T;
      T = q;
      try {
        return it();
      } finally {
        T = k;
      }
    }, i.unstable_scheduleCallback = function(q, it, k) {
      var ct = i.unstable_now();
      switch (typeof k == "object" && k !== null ? (k = k.delay, k = typeof k == "number" && 0 < k ? ct + k : ct) : k = ct, q) {
        case 1:
          var ht = -1;
          break;
        case 2:
          ht = 250;
          break;
        case 5:
          ht = 1073741823;
          break;
        case 4:
          ht = 1e4;
          break;
        default:
          ht = 5e3;
      }
      return ht = k + ht, q = {
        id: g++,
        callback: it,
        priorityLevel: q,
        startTime: k,
        expirationTime: ht,
        sortIndex: -1
      }, k > ct ? (q.sortIndex = k, l(b, q), r(v) === null && q === r(b) && (B ? (Y(J), J = -1) : B = !0, zt(nt, k - ct))) : (q.sortIndex = ht, l(v, q), z || V || (z = !0, rt || (rt = !0, Nt()))), q;
    }, i.unstable_shouldYield = $, i.unstable_wrapCallback = function(q) {
      var it = T;
      return function() {
        var k = T;
        T = it;
        try {
          return q.apply(this, arguments);
        } finally {
          T = k;
        }
      };
    };
  })($c)), $c;
}
var Fp;
function oT() {
  return Fp || (Fp = 1, Ic.exports = uT()), Ic.exports;
}
var tf = { exports: {} }, ce = {};
var Wp;
function rT() {
  if (Wp) return ce;
  Wp = 1;
  var i = Jf();
  function l(g) {
    var p = "https://react.dev/errors/" + g;
    if (1 < arguments.length) {
      p += "?args[]=" + encodeURIComponent(arguments[1]);
      for (var T = 2; T < arguments.length; T++)
        p += "&args[]=" + encodeURIComponent(arguments[T]);
    }
    return "Minified React error #" + g + "; visit " + p + " for the full message or use the non-minified dev environment for full errors and additional helpful warnings.";
  }
  function r() {
  }
  var o = {
    d: {
      f: r,
      r: function() {
        throw Error(l(522));
      },
      D: r,
      C: r,
      L: r,
      m: r,
      X: r,
      S: r,
      M: r
    },
    p: 0,
    findDOMNode: null
  }, c = /* @__PURE__ */ Symbol.for("react.portal"), d = /* @__PURE__ */ Symbol.for("react.recoverable"), h = /* @__PURE__ */ Symbol.for("react.optimistic_key");
  function y(g, p, T) {
    var V = 3 < arguments.length && arguments[3] !== void 0 ? arguments[3] : null;
    return {
      $$typeof: c,
      key: V == null ? null : V === h ? h : "" + V,
      children: g,
      containerInfo: p,
      implementation: T
    };
  }
  var v = i.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;
  function b(g, p) {
    if (g === "font") return "";
    if (typeof p == "string")
      return p === "use-credentials" ? p : "";
  }
  return ce.__DOM_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE = o, ce.browser = function(g) {
    return { $$typeof: d, _reason: g };
  }, ce.createPortal = function(g, p) {
    var T = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null;
    if (!p || p.nodeType !== 1 && p.nodeType !== 9 && p.nodeType !== 11)
      throw Error(l(299));
    return y(g, p, null, T);
  }, ce.flushSync = function(g) {
    var p = v.T, T = o.p;
    try {
      if (v.T = null, o.p = 2, g) return g();
    } finally {
      v.T = p, o.p = T, o.d.f();
    }
  }, ce.preconnect = function(g, p) {
    typeof g == "string" && (p ? (p = p.crossOrigin, p = typeof p == "string" ? p === "use-credentials" ? p : "" : void 0) : p = null, o.d.C(g, p));
  }, ce.prefetchDNS = function(g) {
    typeof g == "string" && o.d.D(g);
  }, ce.preinit = function(g, p) {
    if (typeof g == "string" && p && typeof p.as == "string") {
      var T = p.as, V = b(T, p.crossOrigin), z = typeof p.integrity == "string" ? p.integrity : void 0, B = typeof p.fetchPriority == "string" ? p.fetchPriority : void 0;
      T === "style" ? o.d.S(
        g,
        typeof p.precedence == "string" ? p.precedence : void 0,
        {
          crossOrigin: V,
          integrity: z,
          fetchPriority: B
        }
      ) : T === "script" && o.d.X(g, {
        crossOrigin: V,
        integrity: z,
        fetchPriority: B,
        nonce: typeof p.nonce == "string" ? p.nonce : void 0
      });
    }
  }, ce.preinitModule = function(g, p) {
    if (typeof g == "string")
      if (typeof p == "object" && p !== null) {
        if (p.as == null || p.as === "script") {
          var T = b(
            p.as,
            p.crossOrigin
          );
          o.d.M(g, {
            crossOrigin: T,
            integrity: typeof p.integrity == "string" ? p.integrity : void 0,
            nonce: typeof p.nonce == "string" ? p.nonce : void 0,
            fetchPriority: typeof p.fetchPriority == "string" ? p.fetchPriority : void 0
          });
        }
      } else p == null && o.d.M(g);
  }, ce.preload = function(g, p) {
    if (typeof g == "string" && typeof p == "object" && p !== null && typeof p.as == "string") {
      var T = p.as, V = b(T, p.crossOrigin);
      o.d.L(g, T, {
        crossOrigin: V,
        integrity: typeof p.integrity == "string" ? p.integrity : void 0,
        nonce: typeof p.nonce == "string" ? p.nonce : void 0,
        type: typeof p.type == "string" ? p.type : void 0,
        fetchPriority: typeof p.fetchPriority == "string" ? p.fetchPriority : void 0,
        referrerPolicy: typeof p.referrerPolicy == "string" ? p.referrerPolicy : void 0,
        imageSrcSet: typeof p.imageSrcSet == "string" ? p.imageSrcSet : void 0,
        imageSizes: typeof p.imageSizes == "string" ? p.imageSizes : void 0,
        media: typeof p.media == "string" ? p.media : void 0
      });
    }
  }, ce.preloadModule = function(g, p) {
    if (typeof g == "string")
      if (p) {
        var T = b(p.as, p.crossOrigin);
        o.d.m(g, {
          as: typeof p.as == "string" && p.as !== "script" ? p.as : void 0,
          crossOrigin: T,
          integrity: typeof p.integrity == "string" ? p.integrity : void 0,
          nonce: typeof p.nonce == "string" ? p.nonce : void 0,
          fetchPriority: typeof p.fetchPriority == "string" ? p.fetchPriority : void 0
        });
      } else o.d.m(g);
  }, ce.requestFormReset = function(g) {
    o.d.r(g);
  }, ce.unstable_batchedUpdates = function(g, p) {
    return g(p);
  }, ce.useFormState = function(g, p, T) {
    return v.H.useFormState(g, p, T);
  }, ce.useFormStatus = function() {
    return v.H.useHostTransitionStatus();
  }, ce.version = "19.3.1", ce;
}
var Ip;
function cT() {
  if (Ip) return tf.exports;
  Ip = 1;
  function i() {
    if (!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" || typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function"))
      try {
        __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(i);
      } catch (l) {
        console.error(l);
      }
  }
  return i(), tf.exports = rT(), tf.exports;
}
var $p;
function fT() {
  if ($p) return Jl;
  $p = 1;
  var i = oT(), l = Jf(), r = cT();
  function o(t) {
    var e = "https://react.dev/errors/" + t;
    if (1 < arguments.length) {
      e += "?args[]=" + encodeURIComponent(arguments[1]);
      for (var n = 2; n < arguments.length; n++)
        e += "&args[]=" + encodeURIComponent(arguments[n]);
    }
    return "Minified React error #" + t + "; visit " + e + " for the full message or use the non-minified dev environment for full errors and additional helpful warnings.";
  }
  function c(t) {
    return !(!t || t.nodeType !== 1 && t.nodeType !== 9 && t.nodeType !== 11);
  }
  function d(t) {
    for (var e = t, n = e; n && !n.alternate; )
      e = n, (e.flags & 4098) !== 0 && (t = e.return), n = e.return;
    for (; e.return; ) e = e.return;
    return e.tag === 3 ? t : null;
  }
  function h(t) {
    if (t.tag === 13) {
      var e = t.memoizedState;
      if (e === null && (t = t.alternate, t !== null && (e = t.memoizedState)), e !== null) return e.dehydrated;
    }
    return null;
  }
  function y(t) {
    if (t.tag === 31) {
      var e = t.memoizedState;
      if (e === null && (t = t.alternate, t !== null && (e = t.memoizedState)), e !== null) return e.dehydrated;
    }
    return null;
  }
  function v(t) {
    if (d(t) !== t)
      throw Error(o(188));
  }
  function b(t) {
    var e = t.alternate;
    if (!e) {
      if (e = d(t), e === null) throw Error(o(188));
      return e !== t ? null : t;
    }
    for (var n = t, a = e; ; ) {
      var s = n.return;
      if (s === null) break;
      var u = s.alternate;
      if (u === null) {
        if (a = s.return, a !== null) {
          n = a;
          continue;
        }
        break;
      }
      if (s.child === u.child) {
        for (u = s.child; u; ) {
          if (u === n) return v(s), t;
          if (u === a) return v(s), e;
          u = u.sibling;
        }
        throw Error(o(188));
      }
      if (n.return !== a.return) n = s, a = u;
      else {
        for (var f = !1, m = s.child; m; ) {
          if (m === n) {
            f = !0, n = s, a = u;
            break;
          }
          if (m === a) {
            f = !0, a = s, n = u;
            break;
          }
          m = m.sibling;
        }
        if (!f) {
          for (m = u.child; m; ) {
            if (m === n) {
              f = !0, n = u, a = s;
              break;
            }
            if (m === a) {
              f = !0, a = u, n = s;
              break;
            }
            m = m.sibling;
          }
          if (!f) throw Error(o(189));
        }
      }
      if (n.alternate !== a) throw Error(o(190));
    }
    if (n.tag !== 3) throw Error(o(188));
    return n.stateNode.current === n ? t : e;
  }
  function g(t) {
    var e = t.tag;
    if (e === 5 || e === 26 || e === 27 || e === 6) return t;
    for (t = t.child; t !== null; ) {
      if (e = g(t), e !== null) return e;
      t = t.sibling;
    }
    return null;
  }
  function p(t, e, n, a, s, u) {
    for (; t !== null; ) {
      if ((t.tag === 5 || t.tag === 27 || t.tag === 6) && n(t, a, s, u) || (t.tag !== 22 || t.memoizedState === null) && (e || t.tag !== 5 && t.tag !== 27) && p(
        t.child,
        e,
        n,
        a,
        s,
        u
      ))
        return !0;
      t = t.sibling;
    }
    return !1;
  }
  function T(t) {
    for (t = t.return; t !== null; ) {
      if (t.tag === 3 || t.tag === 5 || t.tag === 27) return t;
      t = t.return;
    }
    return null;
  }
  function V(t) {
    var e = !1;
    for (t = t.return; t !== null && (t.tag === 4 && (e = !0), !(t.tag === 3 || t.tag === 5 || t.tag === 27)); )
      t = t.return;
    return e;
  }
  function z(t) {
    var e = [null, null], n = T(t);
    return n === null || B(
      e,
      t,
      n.child,
      { foundSelf: !1 }
    ), e;
  }
  function B(t, e, n, a) {
    for (; n !== null; ) {
      if (n === e) a.foundSelf = !0;
      else if (n.tag === 5 || n.tag === 27 || n.tag === 6) {
        if (a.foundSelf) return t[1] = n, !0;
        t[0] = n;
      } else if ((n.tag !== 22 || n.memoizedState === null) && B(
        t,
        e,
        n.child,
        a
      ))
        return !0;
      n = n.sibling;
    }
    return !1;
  }
  function j(t) {
    switch (t.tag) {
      case 5:
      case 27:
      case 6:
        return t.stateNode;
      case 3:
        return t.stateNode.containerInfo;
      default:
        throw Error(o(559));
    }
  }
  var L = null, Y = null;
  function U(t, e, n) {
    return t === n ? !0 : t === e ? (L = t, !0) : !1;
  }
  function G(t, e, n) {
    return t === n ? (Y = t, !1) : t === e ? (Y !== null && (L = t), !0) : !1;
  }
  function nt(t) {
    if (t === null) return null;
    do
      t = t === null ? null : t.return;
    while (t && t.tag !== 5 && t.tag !== 27 && t.tag !== 3);
    return t || null;
  }
  function rt(t, e, n) {
    for (var a = 0, s = t; s; s = n(s)) a++;
    s = 0;
    for (var u = e; u; u = n(u)) s++;
    for (; 0 < a - s; ) t = n(t), a--;
    for (; 0 < s - a; ) e = n(e), s--;
    for (; a--; ) {
      if (t === e || e !== null && t === e.alternate)
        return t;
      t = n(t), e = n(e);
    }
    return null;
  }
  var J = Object.assign, Q = /* @__PURE__ */ Symbol.for("react.element"), Ot = /* @__PURE__ */ Symbol.for("react.transitional.element"), $ = /* @__PURE__ */ Symbol.for("react.portal"), vt = /* @__PURE__ */ Symbol.for("react.fragment"), Nt = /* @__PURE__ */ Symbol.for("react.strict_mode"), de = /* @__PURE__ */ Symbol.for("react.profiler"), Wt = /* @__PURE__ */ Symbol.for("react.consumer"), zt = /* @__PURE__ */ Symbol.for("react.context"), q = /* @__PURE__ */ Symbol.for("react.forward_ref"), it = /* @__PURE__ */ Symbol.for("react.suspense"), k = /* @__PURE__ */ Symbol.for("react.suspense_list"), ct = /* @__PURE__ */ Symbol.for("react.memo"), ht = /* @__PURE__ */ Symbol.for("react.lazy"), It = /* @__PURE__ */ Symbol.for("react.activity"), Fe = /* @__PURE__ */ Symbol.for("react.legacy_hidden"), Ta = /* @__PURE__ */ Symbol.for("react.memo_cache_sentinel"), E = /* @__PURE__ */ Symbol.for("react.view_transition"), H = /* @__PURE__ */ Symbol.for("react.recoverable"), tt = Symbol.iterator;
  function et(t) {
    return t === null || typeof t != "object" ? null : (t = tt && t[tt] || t["@@iterator"], typeof t == "function" ? t : null);
  }
  var bt = /* @__PURE__ */ Symbol.for("react.client.reference");
  function St(t) {
    if (t == null) return null;
    if (typeof t == "function")
      return t.$$typeof === bt ? null : t.displayName || t.name || null;
    if (typeof t == "string") return t;
    switch (t) {
      case vt:
        return "Fragment";
      case de:
        return "Profiler";
      case Nt:
        return "StrictMode";
      case it:
        return "Suspense";
      case k:
        return "SuspenseList";
      case It:
        return "Activity";
      case E:
        return "ViewTransition";
    }
    if (typeof t == "object")
      switch (t.$$typeof) {
        case $:
          return "Portal";
        case zt:
          return t.displayName || "Context";
        case Wt:
          return (t._context.displayName || "Context") + ".Consumer";
        case q:
          var e = t.render;
          return t = t.displayName, t || (t = e.displayName || e.name || "", t = t !== "" ? "ForwardRef(" + t + ")" : "ForwardRef"), t;
        case ct:
          return e = t.displayName || null, e !== null ? e : St(t.type) || "Memo";
        case ht:
          e = t._payload, t = t._init;
          try {
            return St(t(e));
          } catch {
          }
      }
    return null;
  }
  var xt = Array.isArray, W = l.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, lt = r.__DOM_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, An = {
    pending: !1,
    data: null,
    method: null,
    action: null
  }, mo = [], Ia = -1;
  function un(t) {
    return { current: t };
  }
  function ae(t) {
    0 > Ia || (t.current = mo[Ia], mo[Ia] = null, Ia--);
  }
  function jt(t, e) {
    Ia++, mo[Ia] = t.current, t.current = e;
  }
  var on = un(null), Ii = un(null), qn = un(null), os = un(null);
  function rs(t, e) {
    switch (jt(qn, e), jt(Ii, t), jt(on, null), e.nodeType) {
      case 9:
      case 11:
        t = (t = e.documentElement) && (t = t.namespaceURI) ? tp(t) : 0;
        break;
      default:
        if (t = e.tagName, e = e.namespaceURI)
          e = tp(e), t = ep(e, t);
        else
          switch (t) {
            case "svg":
              t = 1;
              break;
            case "math":
              t = 2;
              break;
            default:
              t = 0;
          }
    }
    ae(on), jt(on, t);
  }
  function $a() {
    ae(on), ae(Ii), ae(qn);
  }
  function yo(t) {
    var e = t.memoizedState;
    e !== null && (Yi._currentValue = e.memoizedState, jt(os, t)), e = on.current;
    var n = ep(e, t.type);
    e !== n && (jt(Ii, t), jt(on, n));
  }
  function cs(t) {
    Ii.current === t && (ae(on), ae(Ii)), os.current === t && (ae(os), Yi._currentValue = An);
  }
  var po, Th;
  function Gn(t) {
    if (po === void 0)
      try {
        throw Error();
      } catch (n) {
        var e = n.stack.trim().match(/\n( *(at )?)/);
        po = e && e[1] || "", Th = -1 < n.stack.indexOf(`
    at`) ? " (<anonymous>)" : -1 < n.stack.indexOf("@") ? "@unknown:0:0" : "";
      }
    return `
` + po + t + Th;
  }
  var go = !1;
  function vo(t, e) {
    if (!t || go) return "";
    go = !0;
    var n = Error.prepareStackTrace;
    Error.prepareStackTrace = void 0;
    try {
      var a = {
        DetermineComponentFrameRoot: function() {
          try {
            if (e) {
              var w = function() {
                throw Error();
              };
              if (Object.defineProperty(w.prototype, "props", {
                set: function() {
                  throw Error();
                }
              }), typeof Reflect == "object" && Reflect.construct) {
                try {
                  Reflect.construct(w, []);
                } catch (X) {
                  var A = X;
                }
                Reflect.construct(t, [], w);
              } else {
                try {
                  w.call();
                } catch (X) {
                  A = X;
                }
                w = !1;
                try {
                  var O = Object.getOwnPropertyDescriptor(
                    t.prototype,
                    "props"
                  );
                  Object.defineProperty(t.prototype, "props", {
                    configurable: !0,
                    set: function() {
                      throw Error();
                    }
                  }), w = !0, new t();
                } finally {
                  w && (O !== void 0 ? Object.defineProperty(t.prototype, "props", O) : delete t.prototype.props);
                }
              }
            } else {
              try {
                throw Error();
              } catch (X) {
                A = X;
              }
              (w = t()) && typeof w.catch == "function" && w.catch(function() {
              });
            }
          } catch (X) {
            if (X && A && typeof X.stack == "string")
              return [X.stack, A.stack];
          }
          return [null, null];
        }
      };
      a.DetermineComponentFrameRoot.displayName = "DetermineComponentFrameRoot";
      var s = Object.getOwnPropertyDescriptor(
        a.DetermineComponentFrameRoot,
        "name"
      );
      s && s.configurable && Object.defineProperty(
        a.DetermineComponentFrameRoot,
        "name",
        { value: "DetermineComponentFrameRoot" }
      );
      var u = a.DetermineComponentFrameRoot(), f = u[0], m = u[1];
      if (f && m) {
        var S = f.split(`
`), D = m.split(`
`);
        for (s = a = 0; a < S.length && !S[a].includes("DetermineComponentFrameRoot"); )
          a++;
        for (; s < D.length && !D[s].includes(
          "DetermineComponentFrameRoot"
        ); )
          s++;
        if (a === S.length || s === D.length)
          for (a = S.length - 1, s = D.length - 1; 1 <= a && 0 <= s && S[a] !== D[s]; )
            s--;
        for (; 1 <= a && 0 <= s; a--, s--)
          if (S[a] !== D[s]) {
            if (a !== 1 || s !== 1)
              do
                if (a--, s--, 0 > s || S[a] !== D[s]) {
                  var N = `
` + S[a].replace(" at new ", " at ");
                  return t.displayName && N.includes("<anonymous>") && (N = N.replace("<anonymous>", t.displayName)), N;
                }
              while (1 <= a && 0 <= s);
            break;
          }
      }
    } finally {
      go = !1, Error.prepareStackTrace = n;
    }
    return (n = t ? t.displayName || t.name : "") ? Gn(n) : "";
  }
  function s1(t, e) {
    switch (t.tag) {
      case 26:
      case 27:
      case 5:
        return Gn(t.type);
      case 16:
        return Gn("Lazy");
      case 13:
        return t.child !== e && e !== null ? Gn("Suspense Fallback") : Gn("Suspense");
      case 19:
        return Gn("SuspenseList");
      case 0:
      case 15:
        return vo(t.type, !1);
      case 11:
        return vo(t.type.render, !1);
      case 1:
        return vo(t.type, !0);
      case 31:
        return Gn("Activity");
      case 30:
        return Gn("ViewTransition");
      default:
        return "";
    }
  }
  function xh(t) {
    try {
      var e = "", n = null;
      do
        e += s1(t, n), n = t, t = t.return;
      while (t);
      return e;
    } catch (a) {
      return `
Error generating stack: ` + a.message + `
` + a.stack;
    }
  }
  var bo = Object.prototype.hasOwnProperty, So = i.unstable_scheduleCallback, To = i.unstable_cancelCallback, u1 = i.unstable_shouldYield, o1 = i.unstable_requestPaint, Ce = i.unstable_now, r1 = i.unstable_getCurrentPriorityLevel, Eh = i.unstable_ImmediatePriority, Ah = i.unstable_UserBlockingPriority, fs = i.unstable_NormalPriority, c1 = i.unstable_LowPriority, Mh = i.unstable_IdlePriority, f1 = i.log, h1 = i.unstable_setDisableYieldValue, $i = null, Oe = null;
  function Xn(t) {
    if (typeof f1 == "function" && h1(t), Oe && typeof Oe.setStrictMode == "function")
      try {
        Oe.setStrictMode($i, t);
      } catch {
      }
  }
  var Ne = Math.clz32 ? Math.clz32 : y1, d1 = Math.log, m1 = Math.LN2;
  function y1(t) {
    return t >>>= 0, t === 0 ? 32 : 31 - (d1(t) / m1 | 0) | 0;
  }
  var hs = 256, ds = 262144, ms = 4194304;
  function xa(t) {
    var e = t & 42;
    if (e !== 0) return e;
    switch (t & -t) {
      case 1:
        return 1;
      case 2:
        return 2;
      case 4:
        return 4;
      case 8:
        return 8;
      case 16:
        return 16;
      case 32:
        return 32;
      case 64:
        return 64;
      case 128:
        return 128;
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
        return t & -t;
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
        return t & 3932160;
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
        return t & 62914560;
      case 67108864:
        return 67108864;
      case 134217728:
        return 134217728;
      case 268435456:
        return 268435456;
      case 536870912:
        return 536870912;
      case 1073741824:
        return 0;
      default:
        return t;
    }
  }
  function ys(t, e, n) {
    var a = t.pendingLanes;
    if (a === 0) return 0;
    var s = 0, u = t.suspendedLanes, f = t.pingedLanes;
    t = t.warmLanes;
    var m = a & 134217727;
    return m !== 0 ? (a = m & ~u, a !== 0 ? s = xa(a) : (f &= m, f !== 0 ? s = xa(f) : n || (n = m & ~t, n !== 0 && (s = xa(n))))) : (m = a & ~u, m !== 0 ? s = xa(m) : f !== 0 ? s = xa(f) : n || (n = a & ~t, n !== 0 && (s = xa(n)))), s === 0 ? 0 : e !== 0 && e !== s && (e & u) === 0 && (u = s & -s, n = e & -e, u >= n || u === 32 && (n & 4194048) !== 0) ? e : s;
  }
  function tl(t, e) {
    return (t.pendingLanes & ~(t.suspendedLanes & ~t.pingedLanes) & e) === 0;
  }
  function Dh(t, e) {
    (e & 8) !== 0 && (e |= e & 32);
    var n = t.entangledLanes;
    if (n !== 0)
      for (t = t.entanglements, n &= e; 0 < n; ) {
        var a = 31 - Ne(n), s = 1 << a;
        e |= t[a], n &= ~s;
      }
    return e;
  }
  function p1(t, e) {
    switch (t) {
      case 1:
      case 2:
      case 4:
      case 8:
      case 64:
        return e + 250;
      case 16:
      case 32:
      case 128:
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
        return e + 5e3;
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
        return -1;
      case 67108864:
      case 134217728:
      case 268435456:
      case 536870912:
      case 1073741824:
        return -1;
      default:
        return -1;
    }
  }
  function Ch() {
    var t = ms;
    return ms <<= 1, (ms & 62914560) === 0 && (ms = 4194304), t;
  }
  function xo(t) {
    for (var e = [], n = 0; 31 > n; n++) e.push(t);
    return e;
  }
  function el(t, e) {
    t.pendingLanes |= e, e !== 268435456 && (t.suspendedLanes = 0, t.pingedLanes = 0, t.warmLanes = 0);
  }
  function g1(t, e, n, a, s, u) {
    var f = t.pendingLanes;
    t.pendingLanes = n, t.suspendedLanes = 0, t.pingedLanes = 0, t.warmLanes = 0, t.expiredLanes &= n, t.entangledLanes &= n, t.errorRecoveryDisabledLanes &= n, t.shellSuspendCounter = 0;
    var m = t.entanglements, S = t.expirationTimes, D = t.hiddenUpdates;
    for (n = f & ~n; 0 < n; ) {
      var N = 31 - Ne(n), w = 1 << N;
      m[N] = 0, S[N] = -1;
      var A = D[N];
      if (A !== null)
        for (D[N] = null, N = 0; N < A.length; N++) {
          var O = A[N];
          O !== null && (O.lane &= -536870913);
        }
      n &= ~w;
    }
    a !== 0 && Oh(t, a, 0), u !== 0 && s === 0 && t.tag !== 0 && (t.suspendedLanes |= u & ~(f & ~e));
  }
  function Oh(t, e, n) {
    t.pendingLanes |= e, t.suspendedLanes &= ~e;
    var a = 31 - Ne(e);
    t.entangledLanes |= e, t.entanglements[a] = t.entanglements[a] | 1073741824 | n & 261930;
  }
  function Nh(t, e) {
    var n = t.entangledLanes |= e;
    for (t = t.entanglements; n; ) {
      var a = 31 - Ne(n), s = 1 << a;
      s & e | t[a] & e && (t[a] |= e), n &= ~s;
    }
  }
  function zh(t, e) {
    var n = e & -e;
    return n = (n & 42) !== 0 ? 1 : Eo(n), (n & (t.suspendedLanes | e)) !== 0 ? 0 : n;
  }
  function Eo(t) {
    switch (t) {
      case 2:
        t = 1;
        break;
      case 8:
        t = 4;
        break;
      case 32:
        t = 16;
        break;
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
        t = 128;
        break;
      case 268435456:
        t = 134217728;
        break;
      default:
        t = 0;
    }
    return t;
  }
  function Ao(t) {
    return t &= -t, 2 < t ? 8 < t ? (t & 134217727) !== 0 ? 32 : 268435456 : 8 : 2;
  }
  function Rh() {
    var t = lt.p;
    return t !== 0 ? t : (t = window.event, t === void 0 ? 32 : Hp(t.type));
  }
  function _h(t, e) {
    var n = lt.p;
    try {
      return lt.p = t, e();
    } finally {
      lt.p = n;
    }
  }
  var Mn = Math.random().toString(36).slice(2), ie = "__reactFiber$" + Mn, Te = "__reactProps$" + Mn, ti = "__reactContainer$" + Mn, wh = "__reactEvents$" + Mn, v1 = "__reactListeners$" + Mn, b1 = "__reactHandles$" + Mn, Vh = "__reactResources$" + Mn, nl = "__reactMarker$" + Mn, ps = "__reactLoad$" + Mn;
  function gs(t) {
    delete t[ie], delete t[Te], delete t[v1], delete t[b1];
  }
  function Ea(t) {
    var e;
    if (e = t[ie]) return e;
    for (var n = t.parentNode; n; ) {
      if (e = n[ti] || n[ie]) {
        if (n = e.alternate, e.child !== null || n !== null && n.child !== null)
          for (t = vp(t); t !== null; ) {
            if (n = t[ie]) return n;
            t = vp(t);
          }
        return e;
      }
      t = n, n = t.parentNode;
    }
    return null;
  }
  function ei(t) {
    if (t = t[ie] || t[ti]) {
      var e = t.tag;
      if (e === 5 || e === 6 || e === 13 || e === 31 || e === 26 || e === 27 || e === 3)
        return t;
    }
    return null;
  }
  function al(t) {
    var e = t.tag;
    if (e === 5 || e === 26 || e === 27 || e === 6) return t.stateNode;
    throw Error(o(33));
  }
  function ni(t) {
    var e = t[Vh];
    return e || (e = t[Vh] = { hoistableStyles: /* @__PURE__ */ new Map(), hoistableScripts: /* @__PURE__ */ new Map() }), e;
  }
  function $t(t) {
    t[nl] = !0;
  }
  function jh(t) {
    t[ps] = void 0;
  }
  var Uh = /* @__PURE__ */ new Set(), Bh = {};
  function Aa(t, e) {
    ai(t, e), ai(t + "Capture", e);
  }
  function ai(t, e) {
    for (Bh[t] = e, t = 0; t < e.length; t++)
      Uh.add(e[t]);
  }
  var S1 = RegExp(
    "^[:A-Z_a-z\\u00C0-\\u00D6\\u00D8-\\u00F6\\u00F8-\\u02FF\\u0370-\\u037D\\u037F-\\u1FFF\\u200C-\\u200D\\u2070-\\u218F\\u2C00-\\u2FEF\\u3001-\\uD7FF\\uF900-\\uFDCF\\uFDF0-\\uFFFD][:A-Z_a-z\\u00C0-\\u00D6\\u00D8-\\u00F6\\u00F8-\\u02FF\\u0370-\\u037D\\u037F-\\u1FFF\\u200C-\\u200D\\u2070-\\u218F\\u2C00-\\u2FEF\\u3001-\\uD7FF\\uF900-\\uFDCF\\uFDF0-\\uFFFD\\-.0-9\\u00B7\\u0300-\\u036F\\u203F-\\u2040]*$"
  ), Hh = {}, Lh = {};
  function T1(t) {
    return bo.call(Lh, t) ? !0 : bo.call(Hh, t) ? !1 : S1.test(t) ? Lh[t] = !0 : (Hh[t] = !0, !1);
  }
  var Tt = !1;
  function Yh() {
    var t = Tt;
    return Tt = !1, t;
  }
  function vs(t, e, n) {
    if (T1(e))
      if (n === null) t.removeAttribute(e);
      else {
        switch (typeof n) {
          case "undefined":
          case "function":
          case "symbol":
            t.removeAttribute(e);
            return;
          case "boolean":
            var a = e.toLowerCase().slice(0, 5);
            if (a !== "data-" && a !== "aria-") {
              t.removeAttribute(e);
              return;
            }
        }
        t.setAttribute(e, n);
      }
  }
  function bs(t, e, n) {
    if (n === null) t.removeAttribute(e);
    else {
      switch (typeof n) {
        case "undefined":
        case "function":
        case "symbol":
        case "boolean":
          t.removeAttribute(e);
          return;
      }
      t.setAttribute(e, n);
    }
  }
  function Dn(t, e, n, a) {
    if (a === null) t.removeAttribute(n);
    else {
      switch (typeof a) {
        case "undefined":
        case "function":
        case "symbol":
        case "boolean":
          t.removeAttribute(n);
          return;
      }
      t.setAttributeNS(e, n, a);
    }
  }
  function ze(t) {
    switch (typeof t) {
      case "bigint":
      case "boolean":
      case "number":
      case "string":
      case "undefined":
        return t;
      case "object":
        return t;
      default:
        return "";
    }
  }
  function qh(t) {
    var e = t.type;
    return (t = t.nodeName) && t.toLowerCase() === "input" && (e === "checkbox" || e === "radio");
  }
  function x1(t, e, n) {
    var a = Object.getOwnPropertyDescriptor(
      t.constructor.prototype,
      e
    );
    if (!t.hasOwnProperty(e) && typeof a < "u" && typeof a.get == "function" && typeof a.set == "function") {
      var s = a.get, u = a.set;
      return Object.defineProperty(t, e, {
        configurable: !0,
        get: function() {
          return s.call(this);
        },
        set: function(f) {
          n = "" + f, u.call(this, f);
        }
      }), Object.defineProperty(t, e, {
        enumerable: a.enumerable
      }), {
        getValue: function() {
          return n;
        },
        setValue: function(f) {
          n = "" + f;
        },
        stopTracking: function() {
          t._valueTracker = null, delete t[e];
        }
      };
    }
  }
  function Mo(t) {
    if (!t._valueTracker) {
      var e = qh(t) ? "checked" : "value";
      t._valueTracker = x1(
        t,
        e,
        "" + t[e]
      );
    }
  }
  function Gh(t) {
    if (!t) return !1;
    var e = t._valueTracker;
    if (!e) return !0;
    var n = e.getValue(), a = "";
    return t && (a = qh(t) ? t.checked ? "true" : "false" : t.value), t = a, t !== n ? (e.setValue(t), !0) : !1;
  }
  var E1 = /[\n"\\]/g;
  function Le(t) {
    return t.replace(
      E1,
      function(e) {
        return "\\" + e.charCodeAt(0).toString(16) + " ";
      }
    );
  }
  function Do(t, e, n, a, s, u, f, m) {
    t.name = "", f != null && typeof f != "function" && typeof f != "symbol" && typeof f != "boolean" ? t.type = f : t.removeAttribute("type"), e != null ? f === "number" ? (e === 0 && t.value === "" || t.value != e) && (t.value = "" + ze(e)) : t.value !== "" + ze(e) && (t.value = "" + ze(e)) : f !== "submit" && f !== "reset" || t.removeAttribute("value"), e != null ? f === "number" && t.value == e ? Co(t, ze(t.value)) : Co(t, ze(e)) : n != null ? Co(t, ze(n)) : a != null && t.removeAttribute("value"), s == null && u != null && (t.defaultChecked = !!u), s != null && (t.checked = s && typeof s != "function" && typeof s != "symbol"), m != null && typeof m != "function" && typeof m != "symbol" && typeof m != "boolean" ? t.name = "" + ze(m) : t.removeAttribute("name");
  }
  function Xh(t, e, n, a, s, u, f, m) {
    if (u != null && typeof u != "function" && typeof u != "symbol" && typeof u != "boolean" && (t.type = u), e != null || n != null) {
      if (!(u !== "submit" && u !== "reset" || e != null)) {
        Mo(t);
        return;
      }
      n = n != null ? "" + ze(n) : "", e = e != null ? "" + ze(e) : n, m || e === t.value || (t.value = e), t.defaultValue = e;
    }
    a = a ?? s, a = typeof a != "function" && typeof a != "symbol" && !!a, t.checked = m ? t.checked : !!a, t.defaultChecked = !!a, f != null && typeof f != "function" && typeof f != "symbol" && typeof f != "boolean" && (t.name = f), Mo(t);
  }
  function Co(t, e) {
    t.defaultValue !== "" + e && (t.defaultValue = "" + e);
  }
  function ii(t, e, n, a) {
    if (t = t.options, e) {
      e = {};
      for (var s = 0; s < n.length; s++)
        e["$" + n[s]] = !0;
      for (n = 0; n < t.length; n++)
        s = e.hasOwnProperty("$" + t[n].value), t[n].selected !== s && (t[n].selected = s), s && a && (t[n].defaultSelected = !0);
    } else {
      for (n = "" + ze(n), e = null, s = 0; s < t.length; s++) {
        if (t[s].value === n) {
          t[s].selected = !0, a && (t[s].defaultSelected = !0);
          return;
        }
        e !== null || t[s].disabled || (e = t[s]);
      }
      e !== null && (e.selected = !0);
    }
  }
  function Qh(t, e, n) {
    if (e != null && (e = "" + ze(e), e !== t.value && (t.value = e), n == null)) {
      t.defaultValue !== e && (t.defaultValue = e);
      return;
    }
    t.defaultValue = n != null ? "" + ze(n) : "";
  }
  function Zh(t, e, n, a) {
    if (e == null) {
      if (a != null) {
        if (n != null) throw Error(o(92));
        if (xt(a)) {
          if (1 < a.length) throw Error(o(93));
          a = a[0];
        }
        n = a;
      }
      n == null && (n = ""), e = n;
    }
    n = ze(e), t.defaultValue = n, a = t.textContent, a === n && a !== "" && a !== null && (t.value = a), Mo(t);
  }
  function li(t, e) {
    if (e) {
      var n = t.firstChild;
      if (n && n === t.lastChild && n.nodeType === 3) {
        n.nodeValue = e;
        return;
      }
    }
    t.textContent = e;
  }
  var A1 = new Set(
    "animationIterationCount aspectRatio borderImageOutset borderImageSlice borderImageWidth boxFlex boxFlexGroup boxOrdinalGroup columnCount columns flex flexGrow flexPositive flexShrink flexNegative flexOrder gridArea gridRow gridRowEnd gridRowSpan gridRowStart gridColumn gridColumnEnd gridColumnSpan gridColumnStart fontWeight lineClamp lineHeight opacity order orphans scale tabSize widows zIndex zoom fillOpacity floodOpacity stopOpacity strokeDasharray strokeDashoffset strokeMiterlimit strokeOpacity strokeWidth MozAnimationIterationCount MozBoxFlex MozBoxFlexGroup MozLineClamp msAnimationIterationCount msFlex msZoom msFlexGrow msFlexNegative msFlexOrder msFlexPositive msFlexShrink msGridColumn msGridColumnSpan msGridRow msGridRowSpan WebkitAnimationIterationCount WebkitBoxFlex WebKitBoxFlexGroup WebkitBoxOrdinalGroup WebkitColumnCount WebkitColumns WebkitFlex WebkitFlexGrow WebkitFlexPositive WebkitFlexShrink WebkitLineClamp".split(
      " "
    )
  );
  function Kh(t, e, n) {
    var a = e.indexOf("--") === 0;
    n == null || typeof n == "boolean" || n === "" ? a ? t.setProperty(e, "") : e === "float" ? t.cssFloat = "" : t[e] = "" : a ? t.setProperty(e, n) : typeof n != "number" || n === 0 || A1.has(e) ? e === "float" ? t.cssFloat = n : t[e] = ("" + n).trim() : t[e] = n + "px";
  }
  function Jh(t, e, n) {
    if (e != null && typeof e != "object")
      throw Error(o(62));
    if (t = t.style, n != null) {
      for (var a in n)
        !n.hasOwnProperty(a) || e != null && e.hasOwnProperty(a) || (a.indexOf("--") === 0 ? t.setProperty(a, "") : a === "float" ? t.cssFloat = "" : t[a] = "", Tt = !0);
      for (var s in e)
        a = e[s], e.hasOwnProperty(s) && n[s] !== a && (Kh(t, s, a), Tt = !0);
    } else
      for (var u in e)
        e.hasOwnProperty(u) && Kh(t, u, e[u]);
  }
  function Oo(t) {
    if (t.indexOf("-") === -1) return !1;
    switch (t) {
      case "annotation-xml":
      case "color-profile":
      case "font-face":
      case "font-face-src":
      case "font-face-uri":
      case "font-face-format":
      case "font-face-name":
      case "missing-glyph":
        return !1;
      default:
        return !0;
    }
  }
  var M1 = /* @__PURE__ */ new Map([
    ["acceptCharset", "accept-charset"],
    ["htmlFor", "for"],
    ["httpEquiv", "http-equiv"],
    ["crossOrigin", "crossorigin"],
    ["accentHeight", "accent-height"],
    ["alignmentBaseline", "alignment-baseline"],
    ["arabicForm", "arabic-form"],
    ["baselineShift", "baseline-shift"],
    ["capHeight", "cap-height"],
    ["clipPath", "clip-path"],
    ["clipRule", "clip-rule"],
    ["colorInterpolation", "color-interpolation"],
    ["colorInterpolationFilters", "color-interpolation-filters"],
    ["colorProfile", "color-profile"],
    ["colorRendering", "color-rendering"],
    ["dominantBaseline", "dominant-baseline"],
    ["enableBackground", "enable-background"],
    ["fillOpacity", "fill-opacity"],
    ["fillRule", "fill-rule"],
    ["floodColor", "flood-color"],
    ["floodOpacity", "flood-opacity"],
    ["fontFamily", "font-family"],
    ["fontSize", "font-size"],
    ["fontSizeAdjust", "font-size-adjust"],
    ["fontStretch", "font-stretch"],
    ["fontStyle", "font-style"],
    ["fontVariant", "font-variant"],
    ["fontWeight", "font-weight"],
    ["glyphName", "glyph-name"],
    ["glyphOrientationHorizontal", "glyph-orientation-horizontal"],
    ["glyphOrientationVertical", "glyph-orientation-vertical"],
    ["horizAdvX", "horiz-adv-x"],
    ["horizOriginX", "horiz-origin-x"],
    ["imageRendering", "image-rendering"],
    ["letterSpacing", "letter-spacing"],
    ["lightingColor", "lighting-color"],
    ["markerEnd", "marker-end"],
    ["markerMid", "marker-mid"],
    ["markerStart", "marker-start"],
    ["maskType", "mask-type"],
    ["overlinePosition", "overline-position"],
    ["overlineThickness", "overline-thickness"],
    ["paintOrder", "paint-order"],
    ["panose-1", "panose-1"],
    ["pointerEvents", "pointer-events"],
    ["renderingIntent", "rendering-intent"],
    ["shapeRendering", "shape-rendering"],
    ["stopColor", "stop-color"],
    ["stopOpacity", "stop-opacity"],
    ["strikethroughPosition", "strikethrough-position"],
    ["strikethroughThickness", "strikethrough-thickness"],
    ["strokeDasharray", "stroke-dasharray"],
    ["strokeDashoffset", "stroke-dashoffset"],
    ["strokeLinecap", "stroke-linecap"],
    ["strokeLinejoin", "stroke-linejoin"],
    ["strokeMiterlimit", "stroke-miterlimit"],
    ["strokeOpacity", "stroke-opacity"],
    ["strokeWidth", "stroke-width"],
    ["textAnchor", "text-anchor"],
    ["textDecoration", "text-decoration"],
    ["textRendering", "text-rendering"],
    ["transformOrigin", "transform-origin"],
    ["underlinePosition", "underline-position"],
    ["underlineThickness", "underline-thickness"],
    ["unicodeBidi", "unicode-bidi"],
    ["unicodeRange", "unicode-range"],
    ["unitsPerEm", "units-per-em"],
    ["vAlphabetic", "v-alphabetic"],
    ["vHanging", "v-hanging"],
    ["vIdeographic", "v-ideographic"],
    ["vMathematical", "v-mathematical"],
    ["vectorEffect", "vector-effect"],
    ["vertAdvY", "vert-adv-y"],
    ["vertOriginX", "vert-origin-x"],
    ["vertOriginY", "vert-origin-y"],
    ["wordSpacing", "word-spacing"],
    ["writingMode", "writing-mode"],
    ["xmlnsXlink", "xmlns:xlink"],
    ["xHeight", "x-height"]
  ]), D1 = /^[\u0000-\u001F ]*j[\r\n\t]*a[\r\n\t]*v[\r\n\t]*a[\r\n\t]*s[\r\n\t]*c[\r\n\t]*r[\r\n\t]*i[\r\n\t]*p[\r\n\t]*t[\r\n\t]*:/i;
  function Ss(t) {
    return D1.test("" + t) ? "javascript:throw new Error('React has blocked a javascript: URL as a security precaution.')" : t;
  }
  function rn() {
  }
  var No = null;
  function zo(t) {
    return t = t.target || t.srcElement || window, t.correspondingUseElement && (t = t.correspondingUseElement), t.nodeType === 3 ? t.parentNode : t;
  }
  var si = null, ui = null;
  function kh(t) {
    var e = ei(t);
    if (e && (t = e.stateNode)) {
      var n = t[Te] || null;
      t: switch (t = e.stateNode, e.type) {
        case "input":
          if (Do(
            t,
            n.value,
            n.defaultValue,
            n.defaultValue,
            n.checked,
            n.defaultChecked,
            n.type,
            n.name
          ), e = n.name, n.type === "radio" && e != null) {
            for (n = t; n.parentNode; ) n = n.parentNode;
            for (n = n.querySelectorAll(
              'input[name="' + Le(
                "" + e
              ) + '"][type="radio"]'
            ), e = 0; e < n.length; e++) {
              var a = n[e];
              if (a !== t && a.form === t.form) {
                var s = a[Te] || null;
                if (!s) throw Error(o(90));
                Do(
                  a,
                  s.value,
                  s.defaultValue,
                  s.defaultValue,
                  s.checked,
                  s.defaultChecked,
                  s.type,
                  s.name
                );
              }
            }
            for (e = 0; e < n.length; e++)
              a = n[e], a.form === t.form && Gh(a);
          }
          break t;
        case "textarea":
          Qh(t, n.value, n.defaultValue);
          break t;
        case "select":
          e = n.value, e != null && ii(t, !!n.multiple, e, !1);
      }
    }
  }
  var Ro = !1;
  function Ph(t, e, n) {
    if (Ro) return t(e, n);
    Ro = !0;
    try {
      var a = t(e);
      return a;
    } finally {
      if (Ro = !1, (si !== null || ui !== null) && (Su(), si && (e = si, t = ui, ui = si = null, kh(e), t)))
        for (e = 0; e < t.length; e++) kh(t[e]);
    }
  }
  function il(t, e) {
    var n = t.stateNode;
    if (n === null) return null;
    var a = n[Te] || null;
    if (a === null) return null;
    n = a[e];
    t: switch (e) {
      case "onClick":
      case "onClickCapture":
      case "onDoubleClick":
      case "onDoubleClickCapture":
      case "onMouseDown":
      case "onMouseDownCapture":
      case "onMouseMove":
      case "onMouseMoveCapture":
      case "onMouseUp":
      case "onMouseUpCapture":
      case "onMouseEnter":
        (a = !a.disabled) || (t = t.type, a = !(t === "button" || t === "input" || t === "select" || t === "textarea")), t = !a;
        break t;
      default:
        t = !1;
    }
    if (t) return null;
    if (n && typeof n != "function")
      throw Error(
        o(231, e, typeof n)
      );
    return n;
  }
  var Cn = !(typeof window > "u" || typeof window.document > "u" || typeof window.document.createElement > "u"), _o = !1;
  if (Cn)
    try {
      var ll = {};
      Object.defineProperty(ll, "passive", {
        get: function() {
          _o = !0;
        }
      }), window.addEventListener("test", ll, ll), window.removeEventListener("test", ll, ll);
    } catch {
      _o = !1;
    }
  var Qn = null, wo = null, Ts = null;
  function Fh() {
    if (Ts) return Ts;
    var t, e = wo, n = e.length, a, s = "value" in Qn ? Qn.value : Qn.textContent, u = s.length;
    for (t = 0; t < n && e[t] === s[t]; t++) ;
    var f = n - t;
    for (a = 1; a <= f && e[n - a] === s[u - a]; a++) ;
    return Ts = s.slice(t, 1 < a ? 1 - a : void 0);
  }
  function xs(t) {
    var e = t.keyCode;
    return "charCode" in t ? (t = t.charCode, t === 0 && e === 13 && (t = 13)) : t = e, t === 10 && (t = 13), 32 <= t || t === 13 ? t : 0;
  }
  function Es() {
    return !0;
  }
  function Wh() {
    return !1;
  }
  function ye(t) {
    function e(n, a, s, u, f) {
      this._reactName = n, this._targetInst = s, this.type = a, this.nativeEvent = u, this.target = f, this.currentTarget = null;
      for (var m in t)
        t.hasOwnProperty(m) && (n = t[m], this[m] = n ? n(u) : u[m]);
      return this.isDefaultPrevented = (u.defaultPrevented != null ? u.defaultPrevented : u.returnValue === !1) ? Es : Wh, this.isPropagationStopped = Wh, this;
    }
    return J(e.prototype, {
      preventDefault: function() {
        this.defaultPrevented = !0;
        var n = this.nativeEvent;
        n && (n.preventDefault ? n.preventDefault() : typeof n.returnValue != "unknown" && (n.returnValue = !1), this.isDefaultPrevented = Es);
      },
      stopPropagation: function() {
        var n = this.nativeEvent;
        n && (n.stopPropagation ? n.stopPropagation() : typeof n.cancelBubble != "unknown" && (n.cancelBubble = !0), this.isPropagationStopped = Es);
      },
      persist: function() {
      },
      isPersistent: Es
    }), e;
  }
  var Zn = {
    eventPhase: 0,
    bubbles: 0,
    cancelable: 0,
    timeStamp: function(t) {
      return t.timeStamp || Date.now();
    },
    defaultPrevented: 0,
    isTrusted: 0
  }, As = ye(Zn), sl = J({}, Zn, { view: 0, detail: 0 }), C1 = ye(sl), Vo, jo, ul, Ms = J({}, sl, {
    screenX: 0,
    screenY: 0,
    clientX: 0,
    clientY: 0,
    pageX: 0,
    pageY: 0,
    ctrlKey: 0,
    shiftKey: 0,
    altKey: 0,
    metaKey: 0,
    getModifierState: Bo,
    button: 0,
    buttons: 0,
    relatedTarget: function(t) {
      return t.relatedTarget === void 0 ? t.fromElement === t.srcElement ? t.toElement : t.fromElement : t.relatedTarget;
    },
    movementX: function(t) {
      return "movementX" in t ? t.movementX : (t !== ul && (ul && t.type === "mousemove" ? (Vo = t.screenX - ul.screenX, jo = t.screenY - ul.screenY) : jo = Vo = 0, ul = t), Vo);
    },
    movementY: function(t) {
      return "movementY" in t ? t.movementY : jo;
    }
  }), Ih = ye(Ms), O1 = J({}, Ms, { dataTransfer: 0 }), N1 = ye(O1), z1 = J({}, sl, { relatedTarget: 0 }), Uo = ye(z1), R1 = J({}, Zn, {
    animationName: 0,
    elapsedTime: 0,
    pseudoElement: 0
  }), _1 = ye(R1), w1 = J({}, Zn, {
    clipboardData: function(t) {
      return "clipboardData" in t ? t.clipboardData : window.clipboardData;
    }
  }), V1 = ye(w1), j1 = J({}, Zn, { data: 0 }), $h = ye(j1), U1 = {
    Esc: "Escape",
    Spacebar: " ",
    Left: "ArrowLeft",
    Up: "ArrowUp",
    Right: "ArrowRight",
    Down: "ArrowDown",
    Del: "Delete",
    Win: "OS",
    Menu: "ContextMenu",
    Apps: "ContextMenu",
    Scroll: "ScrollLock",
    MozPrintableKey: "Unidentified"
  }, B1 = {
    8: "Backspace",
    9: "Tab",
    12: "Clear",
    13: "Enter",
    16: "Shift",
    17: "Control",
    18: "Alt",
    19: "Pause",
    20: "CapsLock",
    27: "Escape",
    32: " ",
    33: "PageUp",
    34: "PageDown",
    35: "End",
    36: "Home",
    37: "ArrowLeft",
    38: "ArrowUp",
    39: "ArrowRight",
    40: "ArrowDown",
    45: "Insert",
    46: "Delete",
    112: "F1",
    113: "F2",
    114: "F3",
    115: "F4",
    116: "F5",
    117: "F6",
    118: "F7",
    119: "F8",
    120: "F9",
    121: "F10",
    122: "F11",
    123: "F12",
    144: "NumLock",
    145: "ScrollLock",
    224: "Meta"
  }, H1 = {
    Alt: "altKey",
    Control: "ctrlKey",
    Meta: "metaKey",
    Shift: "shiftKey"
  };
  function L1(t) {
    var e = this.nativeEvent;
    return e.getModifierState ? e.getModifierState(t) : (t = H1[t]) ? !!e[t] : !1;
  }
  function Bo() {
    return L1;
  }
  var Y1 = J({}, sl, {
    key: function(t) {
      if (t.key) {
        var e = U1[t.key] || t.key;
        if (e !== "Unidentified") return e;
      }
      return t.type === "keypress" ? (t = xs(t), t === 13 ? "Enter" : String.fromCharCode(t)) : t.type === "keydown" || t.type === "keyup" ? B1[t.keyCode] || "Unidentified" : "";
    },
    code: 0,
    location: 0,
    ctrlKey: 0,
    shiftKey: 0,
    altKey: 0,
    metaKey: 0,
    repeat: 0,
    locale: 0,
    getModifierState: Bo,
    charCode: function(t) {
      return t.type === "keypress" ? xs(t) : 0;
    },
    keyCode: function(t) {
      return t.type === "keydown" || t.type === "keyup" ? t.keyCode : 0;
    },
    which: function(t) {
      return t.type === "keypress" ? xs(t) : t.type === "keydown" || t.type === "keyup" ? t.keyCode : 0;
    }
  }), q1 = ye(Y1), G1 = J({}, Ms, {
    pointerId: 0,
    width: 0,
    height: 0,
    pressure: 0,
    tangentialPressure: 0,
    tiltX: 0,
    tiltY: 0,
    twist: 0,
    pointerType: 0,
    isPrimary: 0
  }), td = ye(G1), X1 = J({}, Zn, { submitter: 0 }), Q1 = ye(X1), Z1 = J({}, sl, {
    touches: 0,
    targetTouches: 0,
    changedTouches: 0,
    altKey: 0,
    metaKey: 0,
    ctrlKey: 0,
    shiftKey: 0,
    getModifierState: Bo
  }), K1 = ye(Z1), J1 = J({}, Zn, {
    propertyName: 0,
    elapsedTime: 0,
    pseudoElement: 0
  }), k1 = ye(J1), P1 = J({}, Ms, {
    deltaX: function(t) {
      return "deltaX" in t ? t.deltaX : "wheelDeltaX" in t ? -t.wheelDeltaX : 0;
    },
    deltaY: function(t) {
      return "deltaY" in t ? t.deltaY : "wheelDeltaY" in t ? -t.wheelDeltaY : "wheelDelta" in t ? -t.wheelDelta : 0;
    },
    deltaZ: 0,
    deltaMode: 0
  }), F1 = ye(P1), W1 = J({}, Zn, {
    newState: 0,
    oldState: 0,
    source: 0
  }), I1 = ye(W1), $1 = [9, 13, 27, 32], Ho = Cn && "CompositionEvent" in window, ol = null;
  Cn && "documentMode" in document && (ol = document.documentMode);
  var tb = Cn && "TextEvent" in window && !ol, ed = Cn && (!Ho || ol && 8 < ol && 11 >= ol), nd = " ", ad = !1;
  function id(t, e) {
    switch (t) {
      case "keyup":
        return $1.indexOf(e.keyCode) !== -1;
      case "keydown":
        return e.keyCode !== 229;
      case "keypress":
      case "mousedown":
      case "focusout":
        return !0;
      default:
        return !1;
    }
  }
  function ld(t) {
    return t = t.detail, typeof t == "object" && "data" in t ? t.data : null;
  }
  var oi = !1;
  function eb(t, e) {
    switch (t) {
      case "compositionend":
        return ld(e);
      case "keypress":
        return e.which !== 32 ? null : (ad = !0, nd);
      case "textInput":
        return t = e.data, t === nd && ad ? null : t;
      default:
        return null;
    }
  }
  function nb(t, e) {
    if (oi)
      return t === "compositionend" || !Ho && id(t, e) ? (t = Fh(), Ts = wo = Qn = null, oi = !1, t) : null;
    switch (t) {
      case "paste":
        return null;
      case "keypress":
        if (!(e.ctrlKey || e.altKey || e.metaKey) || e.ctrlKey && e.altKey) {
          if (e.char && 1 < e.char.length)
            return e.char;
          if (e.which) return String.fromCharCode(e.which);
        }
        return null;
      case "compositionend":
        return ed && e.locale !== "ko" ? null : e.data;
      default:
        return null;
    }
  }
  var ab = {
    color: !0,
    date: !0,
    datetime: !0,
    "datetime-local": !0,
    email: !0,
    month: !0,
    number: !0,
    password: !0,
    range: !0,
    search: !0,
    tel: !0,
    text: !0,
    time: !0,
    url: !0,
    week: !0
  };
  function sd(t) {
    var e = t && t.nodeName && t.nodeName.toLowerCase();
    return e === "input" ? !!ab[t.type] : e === "textarea";
  }
  function ud(t, e, n, a) {
    si ? ui ? ui.push(a) : ui = [a] : si = a, e = Du(e, "onChange"), 0 < e.length && (n = new As(
      "onChange",
      "change",
      null,
      n,
      a
    ), t.push({ event: n, listeners: e }));
  }
  var rl = null, cl = null;
  function ib(t) {
    ky(t, 0);
  }
  function Ds(t) {
    var e = al(t);
    if (Gh(e)) return t;
  }
  function od(t, e) {
    if (t === "change") return e;
  }
  var rd = !1;
  if (Cn) {
    var Lo;
    if (Cn) {
      var Yo = "oninput" in document;
      if (!Yo) {
        var cd = document.createElement("div");
        cd.setAttribute("oninput", "return;"), Yo = typeof cd.oninput == "function";
      }
      Lo = Yo;
    } else Lo = !1;
    rd = Lo && (!document.documentMode || 9 < document.documentMode);
  }
  function fd() {
    rl && (rl.detachEvent("onpropertychange", hd), cl = rl = null);
  }
  function hd(t) {
    if (t.propertyName === "value" && Ds(cl)) {
      var e = [];
      ud(
        e,
        cl,
        t,
        zo(t)
      ), Ph(ib, e);
    }
  }
  function lb(t, e, n) {
    t === "focusin" ? (fd(), rl = e, cl = n, rl.attachEvent("onpropertychange", hd)) : t === "focusout" && fd();
  }
  function sb(t) {
    if (t === "selectionchange" || t === "keyup" || t === "keydown")
      return Ds(cl);
  }
  function ub(t, e) {
    if (t === "click") return Ds(e);
  }
  function ob(t, e) {
    if (t === "input" || t === "change")
      return Ds(e);
  }
  function rb(t, e) {
    return t === e && (t !== 0 || 1 / t === 1 / e) || t !== t && e !== e;
  }
  var Re = typeof Object.is == "function" ? Object.is : rb;
  function fl(t, e) {
    if (Re(t, e)) return !0;
    if (typeof t != "object" || t === null || typeof e != "object" || e === null)
      return !1;
    var n = Object.keys(t), a = Object.keys(e);
    if (n.length !== a.length) return !1;
    for (a = 0; a < n.length; a++) {
      var s = n[a];
      if (!bo.call(e, s) || !Re(t[s], e[s]))
        return !1;
    }
    return !0;
  }
  function qo(t) {
    if (t = t || (typeof document < "u" ? document : void 0), typeof t > "u") return null;
    try {
      return t.activeElement || t.body;
    } catch {
      return t.body;
    }
  }
  function dd(t) {
    for (; t && t.firstChild; ) t = t.firstChild;
    return t;
  }
  function md(t, e) {
    var n = dd(t);
    t = 0;
    for (var a; n; ) {
      if (n.nodeType === 3) {
        if (a = t + n.textContent.length, t <= e && a >= e)
          return { node: n, offset: e - t };
        t = a;
      }
      t: {
        for (; n; ) {
          if (n.nextSibling) {
            n = n.nextSibling;
            break t;
          }
          n = n.parentNode;
        }
        n = void 0;
      }
      n = dd(n);
    }
  }
  function yd(t, e) {
    return t && e ? t === e ? !0 : t && t.nodeType === 3 ? !1 : e && e.nodeType === 3 ? yd(t, e.parentNode) : "contains" in t ? t.contains(e) : t.compareDocumentPosition ? !!(t.compareDocumentPosition(e) & 16) : !1 : !1;
  }
  function pd(t) {
    t = t != null && t.ownerDocument != null && t.ownerDocument.defaultView != null ? t.ownerDocument.defaultView : window;
    for (var e = qo(t.document); e instanceof t.HTMLIFrameElement; ) {
      try {
        var n = typeof e.contentWindow.location.href == "string";
      } catch {
        n = !1;
      }
      if (n) t = e.contentWindow;
      else break;
      e = qo(t.document);
    }
    return e;
  }
  function Go(t) {
    var e = t && t.nodeName && t.nodeName.toLowerCase();
    return e && (e === "input" && (t.type === "text" || t.type === "search" || t.type === "tel" || t.type === "url" || t.type === "password") || e === "textarea" || t.contentEditable === "true");
  }
  var cb = Cn && "documentMode" in document && 11 >= document.documentMode, ri = null, Xo = null, hl = null, Qo = !1;
  function gd(t, e, n) {
    var a = n.window === n ? n.document : n.nodeType === 9 ? n : n.ownerDocument;
    Qo || ri == null || ri !== qo(a) || (a = ri, "selectionStart" in a && Go(a) ? a = { start: a.selectionStart, end: a.selectionEnd } : (a = (a.ownerDocument && a.ownerDocument.defaultView || window).getSelection(), a = {
      anchorNode: a.anchorNode,
      anchorOffset: a.anchorOffset,
      focusNode: a.focusNode,
      focusOffset: a.focusOffset
    }), hl && fl(hl, a) || (hl = a, a = Du(Xo, "onSelect"), 0 < a.length && (e = new As(
      "onSelect",
      "select",
      null,
      e,
      n
    ), t.push({ event: e, listeners: a }), e.target = ri)));
  }
  function Ma(t, e) {
    var n = {};
    return n[t.toLowerCase()] = e.toLowerCase(), n["Webkit" + t] = "webkit" + e, n["Moz" + t] = "moz" + e, n;
  }
  var ci = {
    animationend: Ma("Animation", "AnimationEnd"),
    animationiteration: Ma("Animation", "AnimationIteration"),
    animationstart: Ma("Animation", "AnimationStart"),
    transitionrun: Ma("Transition", "TransitionRun"),
    transitionstart: Ma("Transition", "TransitionStart"),
    transitioncancel: Ma("Transition", "TransitionCancel"),
    transitionend: Ma("Transition", "TransitionEnd")
  }, Zo = {}, vd = {};
  Cn && (vd = document.createElement("div").style, "AnimationEvent" in window || (delete ci.animationend.animation, delete ci.animationiteration.animation, delete ci.animationstart.animation), "TransitionEvent" in window || delete ci.transitionend.transition);
  function Da(t) {
    if (Zo[t]) return Zo[t];
    if (!ci[t]) return t;
    var e = ci[t], n;
    for (n in e)
      if (e.hasOwnProperty(n) && n in vd)
        return Zo[t] = e[n];
    return t;
  }
  var bd = Da("animationend"), Sd = Da("animationiteration"), Td = Da("animationstart"), fb = Da("transitionrun"), hb = Da("transitionstart"), db = Da("transitioncancel"), xd = Da("transitionend"), Ed = /* @__PURE__ */ new Map(), Ko = "abort auxClick beforeToggle cancel canPlay canPlayThrough click close contextMenu copy cut drag dragEnd dragEnter dragExit dragLeave dragOver dragStart drop durationChange emptied encrypted ended error fullscreenChange fullscreenError gotPointerCapture input invalid keyDown keyPress keyUp load loadedData loadedMetadata loadStart lostPointerCapture mouseDown mouseMove mouseOut mouseOver mouseUp paste pause play playing pointerCancel pointerDown pointerMove pointerOut pointerOver pointerUp progress rateChange reset resize seeked seeking stalled submit suspend timeUpdate touchCancel touchEnd touchStart volumeChange scroll toggle touchMove waiting wheel".split(
    " "
  );
  Ko.push("scrollEnd");
  function We(t, e) {
    Ed.set(t, e), Aa(e, [t]);
  }
  var mb = 0;
  function On(t, e) {
    if (t.name != null && t.name !== "auto") return t.name;
    if (e.autoName !== null) return e.autoName;
    t = en.identifierPrefix;
    var n = mb++;
    return t = "_" + t + "t_" + n.toString(32) + "_", e.autoName = t;
  }
  function Ad(t) {
    if (t == null || typeof t == "string")
      return t;
    var e = null, n = zi;
    if (n !== null)
      for (var a = 0; a < n.length; a++) {
        var s = t[n[a]];
        if (s != null) {
          if (s === "none") return "none";
          e = e == null ? s : e + (" " + s);
        }
      }
    return e ?? t.default;
  }
  function Nn(t, e) {
    return t = Ad(t), e = Ad(e), e == null ? t === "auto" ? null : t : e === "auto" ? null : e;
  }
  var Cs = typeof reportError == "function" ? reportError : function(t) {
    if (typeof window == "object" && typeof window.ErrorEvent == "function") {
      var e = new window.ErrorEvent("error", {
        bubbles: !0,
        cancelable: !0,
        message: typeof t == "object" && t !== null && typeof t.message == "string" ? String(t.message) : String(t),
        error: t
      });
      if (!window.dispatchEvent(e)) return;
    } else if (typeof process == "object" && typeof process.emit == "function") {
      process.emit("uncaughtException", t);
      return;
    }
    console.error(t);
  }, Ye = [], fi = 0, Jo = 0;
  function Os() {
    for (var t = fi, e = Jo = fi = 0; e < t; ) {
      var n = Ye[e];
      Ye[e++] = null;
      var a = Ye[e];
      Ye[e++] = null;
      var s = Ye[e];
      Ye[e++] = null;
      var u = Ye[e];
      if (Ye[e++] = null, a !== null && s !== null) {
        var f = a.pending;
        f === null ? s.next = s : (s.next = f.next, f.next = s), a.pending = s;
      }
      u !== 0 && Md(n, s, u);
    }
  }
  function Ns(t, e, n, a) {
    Ye[fi++] = t, Ye[fi++] = e, Ye[fi++] = n, Ye[fi++] = a, Jo |= a, t.lanes |= a, t = t.alternate, t !== null && (t.lanes |= a);
  }
  function ko(t, e, n, a) {
    return Ns(t, e, n, a), zs(t);
  }
  function Ca(t, e) {
    return Ns(t, null, null, e), zs(t);
  }
  function Md(t, e, n) {
    t.lanes |= n;
    var a = t.alternate;
    a !== null && (a.lanes |= n);
    for (var s = !1, u = t.return; u !== null; )
      u.childLanes |= n, a = u.alternate, a !== null && (a.childLanes |= n), u.tag === 22 && (t = u.stateNode, t === null || t._visibility & 1 || (s = !0)), t = u, u = u.return;
    return t.tag === 3 ? (u = t.stateNode, s && e !== null && (s = 31 - Ne(n), t = u.hiddenUpdates, a = t[s], a === null ? t[s] = [e] : a.push(e), e.lane = n | 536870912), u) : null;
  }
  function zs(t) {
    if (50 < Vl)
      throw Vl = 0, bu = null, Error(o(185));
    for (var e = t.return; e !== null; )
      t = e, e = t.return;
    return t.tag === 3 ? t.stateNode : null;
  }
  var hi = {};
  function yb(t, e, n, a) {
    this.tag = t, this.key = n, this.sibling = this.child = this.return = this.stateNode = this.type = this.elementType = null, this.index = 0, this.refCleanup = this.ref = null, this.pendingProps = e, this.dependencies = this.memoizedState = this.updateQueue = this.memoizedProps = null, this.mode = a, this.subtreeFlags = this.flags = 0, this.deletions = null, this.childLanes = this.lanes = 0, this.alternate = null;
  }
  function xe(t, e, n, a) {
    return new yb(t, e, n, a);
  }
  function Po(t) {
    return t = t.prototype, !(!t || !t.isReactComponent);
  }
  function zn(t, e) {
    var n = t.alternate;
    return n === null ? (n = xe(
      t.tag,
      e,
      t.key,
      t.mode
    ), n.elementType = t.elementType, n.type = t.type, n.stateNode = t.stateNode, n.alternate = t, t.alternate = n) : (n.pendingProps = e, n.type = t.type, n.flags = 0, n.subtreeFlags = 0, n.deletions = null), n.flags = t.flags & 1206910976, n.childLanes = t.childLanes, n.lanes = t.lanes, n.child = t.child, n.memoizedProps = t.memoizedProps, n.memoizedState = t.memoizedState, n.updateQueue = t.updateQueue, e = t.dependencies, n.dependencies = e === null ? null : { lanes: e.lanes, firstContext: e.firstContext }, n.sibling = t.sibling, n.index = t.index, n.ref = t.ref, n.refCleanup = t.refCleanup, n;
  }
  function Dd(t, e) {
    t.flags &= 1206910978;
    var n = t.alternate;
    return n === null ? (t.childLanes = 0, t.lanes = e, t.child = null, t.subtreeFlags = 0, t.memoizedProps = null, t.memoizedState = null, t.updateQueue = null, t.dependencies = null, t.stateNode = null) : (t.childLanes = n.childLanes, t.lanes = n.lanes, t.child = n.child, t.subtreeFlags = 0, t.deletions = null, t.memoizedProps = n.memoizedProps, t.memoizedState = n.memoizedState, t.updateQueue = n.updateQueue, t.type = n.type, e = n.dependencies, t.dependencies = e === null ? null : {
      lanes: e.lanes,
      firstContext: e.firstContext
    }), t;
  }
  function Rs(t, e, n, a, s, u) {
    var f = 0;
    if (a = t, typeof a == "function") Po(a) && (f = 1);
    else if (typeof a == "string")
      f = XS(
        t,
        n,
        on.current
      ) ? 26 : t === "html" || t === "head" || t === "body" ? 27 : 5;
    else
      t: switch (a) {
        case It:
          return t = xe(31, n, e, s), t.elementType = It, t.lanes = u, t;
        case vt:
          return Oa(n.children, s, u, e);
        case Nt:
          f = 8, s |= 24;
          break;
        case de:
          return t = xe(12, n, e, s | 2), t.elementType = de, t.lanes = u, t;
        case it:
          return t = xe(13, n, e, s), t.elementType = it, t.lanes = u, t;
        case k:
          return t = xe(19, n, e, s), t.elementType = k, t.lanes = u, t;
        case Fe:
        case E:
          return t = s | 32, t = xe(30, n, e, t), t.elementType = E, t.lanes = u, t.stateNode = {
            autoName: null,
            paired: null,
            clones: null,
            ref: null
          }, t;
        default:
          if (typeof a == "object" && a !== null)
            switch (a.$$typeof) {
              case zt:
                f = 10;
                break t;
              case Wt:
                f = 9;
                break t;
              case q:
                f = 11;
                break t;
              case ct:
                f = 14;
                break t;
              case ht:
                f = 16, a = null;
                break t;
            }
          f = 29, n = Error(
            o(130, t === null ? "null" : typeof t, "")
          ), a = null;
      }
    return e = xe(f, n, e, s), e.elementType = t, e.type = a, e.lanes = u, e;
  }
  function Oa(t, e, n, a) {
    return t = xe(7, t, a, e), t.lanes = n, t;
  }
  function Fo(t, e, n) {
    return t = xe(6, t, null, e), t.lanes = n, t;
  }
  function Cd(t) {
    var e = xe(18, null, null, 0);
    return e.stateNode = t, e;
  }
  function Wo(t, e, n) {
    return e = xe(
      4,
      t.children !== null ? t.children : [],
      t.key,
      e
    ), e.lanes = n, e.stateNode = {
      containerInfo: t.containerInfo,
      pendingChildren: null,
      implementation: t.implementation
    }, e;
  }
  var Od = /* @__PURE__ */ new WeakMap();
  function qe(t, e) {
    if (typeof t == "object" && t !== null) {
      var n = Od.get(t);
      return n !== void 0 ? n : (e = {
        value: t,
        source: e,
        stack: xh(e)
      }, Od.set(t, e), e);
    }
    return {
      value: t,
      source: e,
      stack: xh(e)
    };
  }
  var di = [], mi = 0, _s = null, dl = 0, Ge = [], Xe = 0, Kn = null, cn = 1, fn = "";
  function Rn(t, e) {
    di[mi++] = dl, di[mi++] = _s, _s = t, dl = e;
  }
  function Nd(t, e, n) {
    Ge[Xe++] = cn, Ge[Xe++] = fn, Ge[Xe++] = Kn, Kn = t;
    var a = cn;
    t = fn;
    var s = 32 - Ne(a) - 1;
    a &= ~(1 << s), n += 1;
    var u = 32 - Ne(e) + s;
    if (30 < u) {
      var f = s - s % 5;
      u = (a & (1 << f) - 1).toString(32), a >>= f, s -= f, cn = 1 << 32 - Ne(e) + s | n << s | a, fn = u + t;
    } else
      cn = 1 << u | n << s | a, fn = t;
  }
  function ws(t) {
    t.return !== null && (Rn(t, 1), Nd(t, 1, 0));
  }
  function Io(t) {
    for (; t === _s; )
      _s = di[--mi], di[mi] = null, dl = di[--mi], di[mi] = null;
    for (; t === Kn; )
      Kn = Ge[--Xe], Ge[Xe] = null, fn = Ge[--Xe], Ge[Xe] = null, cn = Ge[--Xe], Ge[Xe] = null;
  }
  function zd(t, e) {
    Ge[Xe++] = cn, Ge[Xe++] = fn, Ge[Xe++] = Kn, cn = e.id, fn = e.overflow, Kn = t;
  }
  var te = null, Ut = null, ft = !1, Jn = null, Qe = !1, $o = Error(o(519));
  function kn(t) {
    var e = Error(
      o(
        418,
        1 < arguments.length && arguments[1] !== void 0 && arguments[1] ? "text" : "HTML",
        ""
      )
    );
    throw ml(qe(e, t)), $o;
  }
  function Rd(t) {
    var e = t.stateNode, n = t.type, a = t.memoizedProps;
    switch (e[ie] = t, e[Te] = a, n) {
      case "dialog":
        mt("cancel", e), mt("close", e);
        break;
      case "iframe":
      case "object":
      case "embed":
        mt("load", e);
        break;
      case "video":
      case "audio":
        for (n = 0; n < Ul.length; n++)
          mt(Ul[n], e);
        break;
      case "source":
        mt("error", e);
        break;
      case "img":
      case "image":
      case "link":
        mt("error", e), mt("load", e);
        break;
      case "details":
        mt("toggle", e);
        break;
      case "input":
        mt("invalid", e), Xh(
          e,
          a.value,
          a.defaultValue,
          a.checked,
          a.defaultChecked,
          a.type,
          a.name,
          !0
        );
        break;
      case "select":
        mt("invalid", e);
        break;
      case "textarea":
        mt("invalid", e), Zh(e, a.value, a.defaultValue, a.children);
    }
    n = a.children, typeof n != "string" && typeof n != "number" && typeof n != "bigint" || e.textContent === "" + n || a.suppressHydrationWarning === !0 || Iy(e.textContent, n) ? (a.popover != null && (mt("beforetoggle", e), mt("toggle", e)), a.onScroll != null && mt("scroll", e), a.onScrollEnd != null && mt("scrollend", e), a.onClick != null && (e.onclick = rn), e = !0) : e = !1, e || kn(t, !0);
  }
  function Vs(t) {
    for (te = t.return; te; )
      switch (te.tag) {
        case 5:
        case 31:
        case 13:
          Qe = !1;
          return;
        case 27:
        case 3:
          Qe = !0;
          return;
        default:
          te = te.return;
      }
  }
  function yi(t) {
    if (t !== te) return !1;
    if (!ft) return Vs(t), ft = !0, !1;
    var e = t.tag, n;
    if ((n = e !== 3 && e !== 27) && ((n = e === 5) && (n = t.type, n = !(n !== "form" && n !== "button") || Nc(t.type, t.memoizedProps)), n = !n), n && Ut && kn(t), Vs(t), e === 13) {
      if (t = t.memoizedState, t = t !== null ? t.dehydrated : null, !t) throw Error(o(317));
      Ut = gp(t);
    } else if (e === 31) {
      if (t = t.memoizedState, t = t !== null ? t.dehydrated : null, !t) throw Error(o(317));
      Ut = gp(t);
    } else
      e === 27 ? (e = Ut, ca(t.type) ? (t = Hc, Hc = null, Ut = t) : Ut = e) : Ut = te ? Ke(t.stateNode.nextSibling) : null;
    return !0;
  }
  function Na() {
    Ut = te = null, ft = !1;
  }
  function tr() {
    var t = Jn;
    return t !== null && (Me === null ? Me = t : Me.push.apply(
      Me,
      t
    ), Jn = null), t;
  }
  function ml(t) {
    Jn === null ? Jn = [t] : Jn.push(t);
  }
  var er = un(null), za = null, _n = null;
  function Pn(t, e, n) {
    jt(er, e._currentValue), e._currentValue = n;
  }
  function wn(t) {
    t._currentValue = er.current, ae(er);
  }
  function js(t, e, n) {
    for (; t !== null; ) {
      var a = t.alternate;
      if ((t.childLanes & e) !== e ? (t.childLanes |= e, a !== null && (a.childLanes |= e)) : a !== null && (a.childLanes & e) !== e && (a.childLanes |= e), t === n) break;
      t = t.return;
    }
  }
  function nr(t, e, n, a) {
    var s = t.child;
    for (s !== null && (s.return = t); s !== null; ) {
      var u = s.dependencies;
      if (u !== null) {
        var f = s.child;
        u = u.firstContext;
        t: for (; u !== null; ) {
          var m = u;
          u = s;
          for (var S = 0; S < e.length; S++)
            if (m.context === e[S]) {
              u.lanes |= n, m = u.alternate, m !== null && (m.lanes |= n), js(
                u.return,
                n,
                t
              ), a || (f = null);
              break t;
            }
          u = m.next;
        }
      } else if (s.tag === 18) {
        if (f = s.return, f === null) throw Error(o(341));
        f.lanes |= n, u = f.alternate, u !== null && (u.lanes |= n), js(f, n, t), f = null;
      } else
        s.tag === 13 && s.memoizedState !== null && s.memoizedState.dehydrated === null ? (s.lanes |= n, f = s.alternate, f !== null && (f.lanes |= n), js(
          s.return,
          n,
          t
        ), f = s.child, f = f !== null ? f.sibling : null) : f = s.child;
      if (f !== null) f.return = s;
      else
        for (f = s; f !== null; ) {
          if (f === t) {
            f = null;
            break;
          }
          if (s = f.sibling, s !== null) {
            s.return = f.return, f = s;
            break;
          }
          f = f.return;
        }
      s = f;
    }
  }
  function Ra(t, e, n, a) {
    t = null;
    for (var s = e, u = !1; s !== null; ) {
      if (!u) {
        if ((s.flags & 524288) !== 0) u = !0;
        else if ((s.flags & 262144) !== 0) break;
      }
      if (s.tag === 10) {
        var f = s.alternate;
        if (f === null) throw Error(o(387));
        if (f = f.memoizedProps, f !== null) {
          var m = s.type;
          Re(s.pendingProps.value, f.value) || (t !== null ? t.push(m) : t = [m]);
        }
      } else if (s === os.current) {
        if (f = s.alternate, f === null) throw Error(o(387));
        f.memoizedState.memoizedState !== s.memoizedState.memoizedState && (t !== null ? t.push(Yi) : t = [Yi]);
      }
      s = s.return;
    }
    return t !== null && nr(
      e,
      t,
      n,
      a
    ), e.flags |= 262144, t !== null;
  }
  function Us(t) {
    for (t = t.firstContext; t !== null; ) {
      if (!Re(
        t.context._currentValue,
        t.memoizedValue
      ))
        return !0;
      t = t.next;
    }
    return !1;
  }
  function _a(t) {
    za = t, _n = null, t = t.dependencies, t !== null && (t.firstContext = null);
  }
  function le(t) {
    return _d(za, t);
  }
  function Bs(t, e) {
    return za === null && _a(t), _d(t, e);
  }
  function _d(t, e) {
    var n = e._currentValue;
    if (e = { context: e, memoizedValue: n, next: null }, _n === null) {
      if (t === null) throw Error(o(308));
      _n = e, t.dependencies = { lanes: 0, firstContext: e }, t.flags |= 524288;
    } else _n = _n.next = e;
    return n;
  }
  var pb = typeof AbortController < "u" ? AbortController : function() {
    var t = [], e = this.signal = {
      aborted: !1,
      addEventListener: function(n, a) {
        t.push(a);
      }
    };
    this.abort = function() {
      e.aborted = !0, t.forEach(function(n) {
        return n();
      });
    };
  }, gb = i.unstable_scheduleCallback, vb = i.unstable_NormalPriority, Qt = {
    $$typeof: zt,
    Consumer: null,
    Provider: null,
    _currentValue: null,
    _currentValue2: null,
    _threadCount: 0
  };
  function ar() {
    return {
      controller: new pb(),
      data: /* @__PURE__ */ new Map(),
      refCount: 0
    };
  }
  function yl(t) {
    t.refCount--, t.refCount === 0 && gb(vb, function() {
      t.controller.abort();
    });
  }
  function wd(t, e) {
    if ((t.pendingLanes & 4194048) !== 0) {
      var n = t.transitionTypes;
      for (n === null && (n = t.transitionTypes = []), t = 0; t < e.length; t++) {
        var a = e[t];
        n.indexOf(a) === -1 && n.push(a);
      }
    }
  }
  var pl = null;
  function bb(t) {
    var e = t.transitionTypes;
    return t.transitionTypes = null, e;
  }
  var gl = null, ir = 0, wa = 0, pi = null;
  function Sb(t, e) {
    if (gl === null) {
      var n = gl = [];
      ir = 0, wa = Sc(), pi = {
        status: "pending",
        value: void 0,
        then: function(a) {
          n.push(a);
        }
      };
    }
    return ir++, e.then(Vd, Vd), e;
  }
  function Vd() {
    if (--ir === 0 && (pl = null, gl !== null)) {
      pi !== null && (pi.status = "fulfilled");
      var t = gl;
      gl = null, wa = 0, pi = null;
      for (var e = 0; e < t.length; e++) (0, t[e])();
    }
  }
  function Tb(t, e) {
    var n = [], a = {
      status: "pending",
      value: null,
      reason: null,
      then: function(s) {
        n.push(s);
      }
    };
    return t.then(
      function() {
        a.status = "fulfilled", a.value = e;
        for (var s = 0; s < n.length; s++) (0, n[s])(e);
      },
      function(s) {
        for (a.status = "rejected", a.reason = s, s = 0; s < n.length; s++)
          (0, n[s])(void 0);
      }
    ), a;
  }
  var jd = W.S;
  W.S = function(t, e) {
    if (Cy = Ce(), typeof e == "object" && e !== null && typeof e.then == "function" && Sb(t, e), pl !== null)
      for (var n = Vi; n !== null; )
        wd(n, pl), n = n.next;
    if (n = t.types, n !== null) {
      for (var a = Vi; a !== null; )
        wd(a, n), a = a.next;
      if (wa !== 0) {
        a = pl, a === null && (a = pl = []);
        for (var s = 0; s < n.length; s++) {
          var u = n[s];
          a.indexOf(u) === -1 && a.push(u);
        }
      }
    }
    jd !== null && jd(t, e);
  };
  var Va = un(null);
  function lr() {
    var t = Va.current;
    return t !== null ? t : _t.pooledCache;
  }
  function Hs(t, e) {
    e === null ? jt(Va, Va.current) : jt(Va, e.pool);
  }
  function Ud() {
    var t = lr();
    return t === null ? null : { parent: Qt._currentValue, pool: t };
  }
  var gi = Error(o(460)), sr = Error(o(474)), Ls = Error(o(542)), Ys = { then: function() {
  } };
  function Bd(t) {
    return t = t.status, t === "fulfilled" || t === "rejected";
  }
  function Hd(t, e, n) {
    switch (n = t[n], n === void 0 ? t.push(e) : n !== e && (e.then(rn, rn), e = n), e.status) {
      case "fulfilled":
        return e.value;
      case "rejected":
        throw t = e.reason, Yd(t), t === void 0 && !("reason" in e) ? Error(o(600)) : t;
      default:
        if (typeof e.status == "string") e.then(rn, rn);
        else {
          if (t = _t, t !== null && 100 < t.shellSuspendCounter)
            throw Error(o(482));
          t = e, t.status = "pending", t.then(
            function(a) {
              if (e.status === "pending") {
                var s = e;
                s.status = "fulfilled", s.value = a;
              }
            },
            function(a) {
              if (e.status === "pending") {
                var s = e;
                s.status = "rejected", s.reason = a;
              }
            }
          );
        }
        switch (e.status) {
          case "fulfilled":
            return e.value;
          case "rejected":
            throw t = e.reason, Yd(t), t;
        }
        throw Ua = e, gi;
    }
  }
  function ja(t) {
    try {
      var e = t._init;
      return e(t._payload);
    } catch (n) {
      throw n !== null && typeof n == "object" && typeof n.then == "function" ? (Ua = n, gi) : n;
    }
  }
  var Ua = null;
  function Ld() {
    if (Ua === null) throw Error(o(459));
    var t = Ua;
    return Ua = null, t;
  }
  function Yd(t) {
    if (t === gi || t === Ls)
      throw Error(o(483));
  }
  var vi = null, vl = 0;
  function qs(t) {
    var e = vl;
    return vl += 1, vi === null && (vi = []), Hd(vi, t, e);
  }
  function Fn(t, e) {
    e = e.props.ref, t.ref = e !== void 0 ? e : null;
  }
  function Gs(t, e) {
    throw e.$$typeof === Q ? Error(o(525)) : (t = Object.prototype.toString.call(e), Error(
      o(
        31,
        t === "[object Object]" ? "object with keys {" + Object.keys(e).join(", ") + "}" : t
      )
    ));
  }
  function qd(t) {
    function e(M, x) {
      if (t) {
        var C = M.deletions;
        C === null ? (M.deletions = [x], M.flags |= 16) : C.push(x);
      }
    }
    function n(M, x) {
      if (!t) return null;
      for (; x !== null; )
        e(M, x), x = x.sibling;
      return null;
    }
    function a(M) {
      for (var x = /* @__PURE__ */ new Map(); M !== null; )
        M.key === null ? x.set(M.index, M) : x.set(M.key, M), M = M.sibling;
      return x;
    }
    function s(M, x) {
      return M = zn(M, x), M.index = 0, M.sibling = null, M;
    }
    function u(M, x, C) {
      return M.index = C, t ? (C = M.alternate, C !== null ? (C = C.index, C < x ? (M.flags |= 2, x) : C) : (M.flags |= 134217730, x)) : (M.flags |= 1048576, x);
    }
    function f(M) {
      return t && M.alternate === null && (M.flags |= 134217730), M;
    }
    function m(M, x, C, _) {
      return x === null || x.tag !== 6 ? (x = Fo(C, M.mode, _), x.return = M, x) : (x = s(x, C), x.return = M, x);
    }
    function S(M, x, C, _) {
      var Z = C.type;
      return Z === vt ? (M = N(
        M,
        x,
        C.props.children,
        _,
        C.key
      ), Fn(M, C), M) : x !== null && (x.elementType === Z || typeof Z == "object" && Z !== null && Z.$$typeof === ht && ja(Z) === x.type) ? (x = s(x, C.props), Fn(x, C), x.return = M, x) : (x = Rs(
        C.type,
        C.key,
        C.props,
        null,
        M.mode,
        _
      ), Fn(x, C), x.return = M, x);
    }
    function D(M, x, C, _) {
      return x === null || x.tag !== 4 || x.stateNode.containerInfo !== C.containerInfo || x.stateNode.implementation !== C.implementation ? (x = Wo(C, M.mode, _), x.return = M, x) : (x = s(x, C.children || []), x.return = M, x);
    }
    function N(M, x, C, _, Z) {
      return x === null || x.tag !== 7 ? (x = Oa(
        C,
        M.mode,
        _,
        Z
      ), x.return = M, x) : (x = s(x, C), x.return = M, x);
    }
    function w(M, x, C) {
      if (typeof x == "string" && x !== "" || typeof x == "number" || typeof x == "bigint")
        return x = Fo(
          "" + x,
          M.mode,
          C
        ), x.return = M, x;
      if (typeof x == "object" && x !== null) {
        switch (x.$$typeof) {
          case Ot:
            return C = Rs(
              x.type,
              x.key,
              x.props,
              null,
              M.mode,
              C
            ), Fn(C, x), C.return = M, C;
          case $:
            return x = Wo(
              x,
              M.mode,
              C
            ), x.return = M, x;
          case ht:
            return x = ja(x), w(M, x, C);
        }
        if (xt(x) || et(x))
          return x = Oa(
            x,
            M.mode,
            C,
            null
          ), x.return = M, x;
        if (typeof x.then == "function")
          return w(M, qs(x), C);
        if (x.$$typeof === zt)
          return w(
            M,
            Bs(M, x),
            C
          );
        Gs(M, x);
      }
      return null;
    }
    function A(M, x, C, _) {
      var Z = x !== null ? x.key : null;
      if (typeof C == "string" && C !== "" || typeof C == "number" || typeof C == "bigint")
        return Z !== null ? null : m(M, x, "" + C, _);
      if (typeof C == "object" && C !== null) {
        switch (C.$$typeof) {
          case Ot:
            return C.key === Z ? S(M, x, C, _) : null;
          case $:
            return C.key === Z ? D(M, x, C, _) : null;
          case ht:
            return C = ja(C), A(M, x, C, _);
        }
        if (xt(C) || et(C))
          return Z !== null ? null : N(M, x, C, _, null);
        if (typeof C.then == "function")
          return A(
            M,
            x,
            qs(C),
            _
          );
        if (C.$$typeof === zt)
          return A(
            M,
            x,
            Bs(M, C),
            _
          );
        Gs(M, C);
      }
      return null;
    }
    function O(M, x, C, _, Z) {
      if (typeof _ == "string" && _ !== "" || typeof _ == "number" || typeof _ == "bigint")
        return M = M.get(C) || null, m(x, M, "" + _, Z);
      if (typeof _ == "object" && _ !== null) {
        switch (_.$$typeof) {
          case Ot:
            return M = M.get(
              _.key === null ? C : _.key
            ) || null, S(x, M, _, Z);
          case $:
            return M = M.get(
              _.key === null ? C : _.key
            ) || null, D(x, M, _, Z);
          case ht:
            return _ = ja(_), O(
              M,
              x,
              C,
              _,
              Z
            );
        }
        if (xt(_) || et(_))
          return M = M.get(C) || null, N(x, M, _, Z, null);
        if (typeof _.then == "function")
          return O(
            M,
            x,
            C,
            qs(_),
            Z
          );
        if (_.$$typeof === zt)
          return O(
            M,
            x,
            C,
            Bs(x, _),
            Z
          );
        Gs(x, _);
      }
      return null;
    }
    function X(M, x, C, _) {
      for (var Z = null, pt = null, I = x, at = x = 0, Jt = null; I !== null && at < C.length; at++) {
        I.index > at ? (Jt = I, I = null) : Jt = I.sibling;
        var gt = A(
          M,
          I,
          C[at],
          _
        );
        if (gt === null) {
          I === null && (I = Jt);
          break;
        }
        t && I && gt.alternate === null && e(M, I), x = u(gt, x, at), pt === null ? Z = gt : pt.sibling = gt, pt = gt, I = Jt;
      }
      if (at === C.length)
        return n(M, I), ft && Rn(M, at), Z;
      if (I === null) {
        for (; at < C.length; at++)
          I = w(M, C[at], _), I !== null && (x = u(
            I,
            x,
            at
          ), pt === null ? Z = I : pt.sibling = I, pt = I);
        return ft && Rn(M, at), Z;
      }
      for (I = a(I); at < C.length; at++)
        Jt = O(
          I,
          M,
          at,
          C[at],
          _
        ), Jt !== null && (t && (gt = Jt.alternate, gt !== null && I.delete(gt.key === null ? at : gt.key)), x = u(
          Jt,
          x,
          at
        ), pt === null ? Z = Jt : pt.sibling = Jt, pt = Jt);
      return t && I.forEach(function(ya) {
        return e(M, ya);
      }), ft && Rn(M, at), Z;
    }
    function P(M, x, C, _) {
      if (C == null) throw Error(o(151));
      for (var Z = null, pt = null, I = x, at = x = 0, Jt = null, gt = C.next(); I !== null && !gt.done; at++, gt = C.next()) {
        I.index > at ? (Jt = I, I = null) : Jt = I.sibling;
        var ya = A(M, I, gt.value, _);
        if (ya === null) {
          I === null && (I = Jt);
          break;
        }
        t && I && ya.alternate === null && e(M, I), x = u(ya, x, at), pt === null ? Z = ya : pt.sibling = ya, pt = ya, I = Jt;
      }
      if (gt.done)
        return n(M, I), ft && Rn(M, at), Z;
      if (I === null) {
        for (; !gt.done; at++, gt = C.next())
          gt = w(M, gt.value, _), gt !== null && (x = u(gt, x, at), pt === null ? Z = gt : pt.sibling = gt, pt = gt);
        return ft && Rn(M, at), Z;
      }
      for (I = a(I); !gt.done; at++, gt = C.next())
        gt = O(I, M, at, gt.value, _), gt !== null && (t && (Jt = gt.alternate, Jt !== null && I.delete(
          Jt.key === null ? at : Jt.key
        )), x = u(gt, x, at), pt === null ? Z = gt : pt.sibling = gt, pt = gt);
      return t && I.forEach(function(eT) {
        return e(M, eT);
      }), ft && Rn(M, at), Z;
    }
    function ot(M, x, C, _) {
      if (typeof C == "object" && C !== null && C.type === vt && C.key === null && C.props.ref === void 0 && (C = C.props.children), typeof C == "object" && C !== null) {
        switch (C.$$typeof) {
          case Ot:
            t: {
              for (var Z = C.key; x !== null; ) {
                if (x.key === Z) {
                  if (Z = C.type, Z === vt) {
                    if (x.tag === 7) {
                      n(
                        M,
                        x.sibling
                      ), _ = s(
                        x,
                        C.props.children
                      ), Fn(_, C), _.return = M, M = _;
                      break t;
                    }
                  } else if (x.elementType === Z || typeof Z == "object" && Z !== null && Z.$$typeof === ht && ja(Z) === x.type) {
                    n(
                      M,
                      x.sibling
                    ), _ = s(x, C.props), Fn(_, C), _.return = M, M = _;
                    break t;
                  }
                  n(M, x);
                  break;
                } else e(M, x);
                x = x.sibling;
              }
              C.type === vt ? (_ = Oa(
                C.props.children,
                M.mode,
                _,
                C.key
              ), Fn(_, C), _.return = M, M = _) : (_ = Rs(
                C.type,
                C.key,
                C.props,
                null,
                M.mode,
                _
              ), Fn(_, C), _.return = M, M = _);
            }
            return f(M);
          case $:
            t: {
              for (Z = C.key; x !== null; ) {
                if (x.key === Z)
                  if (x.tag === 4 && x.stateNode.containerInfo === C.containerInfo && x.stateNode.implementation === C.implementation) {
                    n(
                      M,
                      x.sibling
                    ), _ = s(x, C.children || []), _.return = M, M = _;
                    break t;
                  } else {
                    n(M, x);
                    break;
                  }
                else e(M, x);
                x = x.sibling;
              }
              _ = Wo(C, M.mode, _), _.return = M, M = _;
            }
            return f(M);
          case ht:
            return C = ja(C), ot(
              M,
              x,
              C,
              _
            );
        }
        if (xt(C))
          return X(
            M,
            x,
            C,
            _
          );
        if (et(C)) {
          if (Z = et(C), typeof Z != "function") throw Error(o(150));
          return C = Z.call(C), P(
            M,
            x,
            C,
            _
          );
        }
        if (typeof C.then == "function")
          return ot(
            M,
            x,
            qs(C),
            _
          );
        if (C.$$typeof === zt)
          return ot(
            M,
            x,
            Bs(M, C),
            _
          );
        Gs(M, C);
      }
      return typeof C == "string" && C !== "" || typeof C == "number" || typeof C == "bigint" ? (C = "" + C, x !== null && x.tag === 6 ? (n(M, x.sibling), _ = s(x, C), _.return = M, M = _) : (n(M, x), _ = Fo(C, M.mode, _), _.return = M, M = _), f(M)) : n(M, x);
    }
    return function(M, x, C, _) {
      try {
        vl = 0;
        var Z = ot(
          M,
          x,
          C,
          _
        );
        return vi = null, Z;
      } catch (I) {
        if (I === gi || I === Ls) throw I;
        var pt = xe(29, I, null, M.mode);
        return pt.lanes = _, pt.return = M, pt;
      }
    };
  }
  var Ba = qd(!0), Gd = qd(!1), Wn = !1;
  function ur(t) {
    t.updateQueue = {
      baseState: t.memoizedState,
      firstBaseUpdate: null,
      lastBaseUpdate: null,
      shared: { pending: null, lanes: 0, hiddenCallbacks: null },
      callbacks: null
    };
  }
  function or(t, e) {
    t = t.updateQueue, e.updateQueue === t && (e.updateQueue = {
      baseState: t.baseState,
      firstBaseUpdate: t.firstBaseUpdate,
      lastBaseUpdate: t.lastBaseUpdate,
      shared: t.shared,
      callbacks: null
    });
  }
  function In(t) {
    return { lane: t, tag: 0, payload: null, callback: null, next: null };
  }
  function $n(t, e, n) {
    var a = t.updateQueue;
    if (a === null) return null;
    if (a = a.shared, (Et & 2) !== 0) {
      var s = a.pending;
      return s === null ? e.next = e : (e.next = s.next, s.next = e), a.pending = e, e = zs(t), Md(t, null, n), e;
    }
    return Ns(t, a, e, n), zs(t);
  }
  function bl(t, e, n) {
    if (e = e.updateQueue, e !== null && (e = e.shared, (n & 4194048) !== 0)) {
      var a = e.lanes;
      a &= t.pendingLanes, n |= a, e.lanes = n, Nh(t, n);
    }
  }
  function rr(t, e) {
    var n = t.updateQueue, a = t.alternate;
    if (a !== null && (a = a.updateQueue, n === a)) {
      var s = null, u = null;
      if (n = n.firstBaseUpdate, n !== null) {
        do {
          var f = {
            lane: n.lane,
            tag: n.tag,
            payload: n.payload,
            callback: null,
            next: null
          };
          u === null ? s = u = f : u = u.next = f, n = n.next;
        } while (n !== null);
        u === null ? s = u = e : u = u.next = e;
      } else s = u = e;
      n = {
        baseState: a.baseState,
        firstBaseUpdate: s,
        lastBaseUpdate: u,
        shared: a.shared,
        callbacks: a.callbacks
      }, t.updateQueue = n;
      return;
    }
    t = n.lastBaseUpdate, t === null ? n.firstBaseUpdate = e : t.next = e, n.lastBaseUpdate = e;
  }
  var cr = !1;
  function Sl() {
    if (cr) {
      var t = pi;
      if (t !== null) throw t;
    }
  }
  function Tl(t, e, n, a) {
    cr = !1;
    var s = t.updateQueue;
    Wn = !1;
    var u = s.firstBaseUpdate, f = s.lastBaseUpdate, m = s.shared.pending;
    if (m !== null) {
      s.shared.pending = null;
      var S = m, D = S.next;
      S.next = null, f === null ? u = D : f.next = D, f = S;
      var N = t.alternate;
      N !== null && (N = N.updateQueue, m = N.lastBaseUpdate, m !== f && (m === null ? N.firstBaseUpdate = D : m.next = D, N.lastBaseUpdate = S));
    }
    if (u !== null) {
      var w = s.baseState;
      f = 0, N = D = S = null, m = u;
      do {
        var A = m.lane & -536870913, O = A !== m.lane;
        if (O ? (yt & A) === A : (a & A) === A) {
          A !== 0 && A === wa && (cr = !0), N !== null && (N = N.next = {
            lane: 0,
            tag: m.tag,
            payload: m.payload,
            callback: null,
            next: null
          });
          t: {
            var X = t, P = m;
            A = e;
            var ot = n;
            switch (P.tag) {
              case 1:
                if (X = P.payload, typeof X == "function") {
                  w = X.call(ot, w, A);
                  break t;
                }
                w = X;
                break t;
              case 3:
                X.flags = X.flags & -65537 | 128;
              case 0:
                if (X = P.payload, A = typeof X == "function" ? X.call(ot, w, A) : X, A == null) break t;
                w = J({}, w, A);
                break t;
              case 2:
                Wn = !0;
            }
          }
          A = m.callback, A !== null && (t.flags |= 64, O && (t.flags |= 8192), O = s.callbacks, O === null ? s.callbacks = [A] : O.push(A));
        } else
          O = {
            lane: A,
            tag: m.tag,
            payload: m.payload,
            callback: m.callback,
            next: null
          }, N === null ? (D = N = O, S = w) : N = N.next = O, f |= A;
        if (m = m.next, m === null) {
          if (m = s.shared.pending, m === null)
            break;
          O = m, m = O.next, O.next = null, s.lastBaseUpdate = O, s.shared.pending = null;
        }
      } while (!0);
      N === null && (S = w), s.baseState = S, s.firstBaseUpdate = D, s.lastBaseUpdate = N, u === null && (s.shared.lanes = 0), sa |= f, t.lanes = f, t.memoizedState = w;
    }
  }
  function Xd(t, e) {
    if (typeof t != "function")
      throw Error(o(191, t));
    t.call(e);
  }
  function Qd(t, e) {
    var n = t.callbacks;
    if (n !== null)
      for (t.callbacks = null, t = 0; t < n.length; t++)
        Xd(n[t], e);
  }
  var ta = un(null), Xs = un(0);
  function Zd(t, e) {
    t = Hn, jt(Xs, t), jt(ta, e), Hn = t | e.baseLanes;
  }
  function fr() {
    jt(Xs, Hn), jt(ta, ta.current);
  }
  function hr() {
    Hn = Xs.current, ae(ta), ae(Xs);
  }
  var se = un(null), me = null;
  function ea(t) {
    var e = t.alternate;
    jt(ue, ue.current & 1), jt(se, t), me === null && (e === null || ta.current !== null || e.memoizedState !== null) && (me = t);
  }
  function dr(t) {
    jt(ue, ue.current), jt(se, t), me === null && (me = t);
  }
  function Kd(t) {
    t.tag === 22 ? (jt(ue, ue.current), jt(se, t), me === null && (me = t)) : na();
  }
  function na() {
    jt(ue, ue.current), jt(se, se.current);
  }
  function _e(t) {
    ae(se), me === t && (me = null), ae(ue);
  }
  var ue = un(0);
  function xl(t, e) {
    jt(se, se.current), jt(ue, e);
  }
  function mr(t) {
    ae(ue), ae(se), me === t && (me = null);
  }
  function Qs(t) {
    for (var e = t; e !== null; ) {
      if (e.tag === 13) {
        var n = e.memoizedState;
        if (n !== null && (n = n.dehydrated, n === null || Uc(n) || Bc(n)))
          return e;
      } else if (e.tag === 19 && e.memoizedProps.revealOrder !== "independent") {
        if ((e.flags & 128) !== 0) return e;
      } else if (e.child !== null) {
        e.child.return = e, e = e.child;
        continue;
      }
      if (e === t) break;
      for (; e.sibling === null; ) {
        if (e.return === null || e.return === t) return null;
        e = e.return;
      }
      e.sibling.return = e.return, e = e.sibling;
    }
    return null;
  }
  var Vn = 0, ut = null, Rt = null, Zt = null, Zs = !1, bi = !1, Ha = !1, Ks = 0, El = 0, Si = null, xb = 0;
  function Yt() {
    throw Error(o(321));
  }
  function yr(t, e) {
    if (e === null) return !1;
    for (var n = 0; n < e.length && n < t.length; n++)
      if (!Re(t[n], e[n])) return !1;
    return !0;
  }
  function pr(t, e, n, a, s, u) {
    return Vn = u, ut = e, e.memoizedState = null, e.updateQueue = null, e.lanes = 0, W.H = t === null || t.memoizedState === null ? Nm : zm, Ha = !1, u = n(a, s), Ha = !1, bi && (u = kd(
      e,
      n,
      a,
      s
    )), Jd(t), u;
  }
  function Jd(t) {
    W.H = $s;
    var e = Rt !== null && Rt.next !== null;
    if (Vn = 0, Zt = Rt = ut = null, Zs = !1, El = 0, Si = null, e) throw Error(o(300));
    t === null || Kt || (t = t.dependencies, t !== null && Us(t) && (Kt = !0));
  }
  function kd(t, e, n, a) {
    ut = t;
    var s = 0;
    do {
      if (bi && (Si = null), El = 0, bi = !1, 25 <= s) throw Error(o(301));
      if (s += 1, Zt = Rt = null, t.updateQueue != null) {
        var u = t.updateQueue;
        u.lastEffect = null, u.events = null, u.stores = null, u.memoCache != null && (u.memoCache.index = 0);
      }
      W.H = zb, u = e(n, a);
    } while (bi);
    return u;
  }
  function Eb() {
    var t = W.H, e = t.useState()[0];
    return e = typeof e.then == "function" ? Al(e) : e, t = t.useState()[0], (Rt !== null ? Rt.memoizedState : null) !== t && (ut.flags |= 1024), e;
  }
  function gr() {
    var t = Ks !== 0;
    return Ks = 0, t;
  }
  function vr(t, e, n) {
    e.updateQueue = t.updateQueue, e.flags &= -2053, t.lanes &= ~n;
  }
  function br(t) {
    if (Zs) {
      for (t = t.memoizedState; t !== null; ) {
        var e = t.queue;
        e !== null && (e.pending = null), t = t.next;
      }
      Zs = !1;
    }
    Vn = 0, Zt = Rt = ut = null, bi = !1, El = Ks = 0, Si = null;
  }
  function pe() {
    var t = {
      memoizedState: null,
      baseState: null,
      baseQueue: null,
      queue: null,
      next: null
    };
    return Zt === null ? ut.memoizedState = Zt = t : Zt = Zt.next = t, Zt;
  }
  function Xt() {
    if (Rt === null) {
      var t = ut.alternate;
      t = t !== null ? t.memoizedState : null;
    } else t = Rt.next;
    var e = Zt === null ? ut.memoizedState : Zt.next;
    if (e !== null)
      Zt = e, Rt = t;
    else {
      if (t === null)
        throw ut.alternate === null ? Error(o(467)) : Error(o(310));
      Rt = t, t = {
        memoizedState: Rt.memoizedState,
        baseState: Rt.baseState,
        baseQueue: Rt.baseQueue,
        queue: Rt.queue,
        next: null
      }, Zt === null ? ut.memoizedState = Zt = t : Zt = Zt.next = t;
    }
    return Zt;
  }
  function Js() {
    return { lastEffect: null, events: null, stores: null, memoCache: null };
  }
  function Al(t) {
    var e = El;
    return El += 1, Si === null && (Si = []), t = Hd(Si, t, e), e = ut, (Zt === null ? e.memoizedState : Zt.next) === null && (e = e.alternate, W.H = e === null || e.memoizedState === null ? Nm : zm), t;
  }
  function ks(t) {
    if (t !== null && typeof t == "object") {
      if (typeof t.then == "function") return Al(t);
      if (t.$$typeof === H) return;
      if (t.$$typeof === zt) return le(t);
    }
    throw Error(o(438, String(t)));
  }
  function Sr(t) {
    var e = null, n = ut.updateQueue;
    if (n !== null && (e = n.memoCache), e == null) {
      var a = ut.alternate;
      a !== null && (a = a.updateQueue, a !== null && (a = a.memoCache, a != null && (e = {
        data: a.data.map(function(s) {
          return s.slice();
        }),
        index: 0
      })));
    }
    if (e == null && (e = { data: [], index: 0 }), n === null && (n = Js(), ut.updateQueue = n), n.memoCache = e, n = e.data[e.index], n === void 0)
      for (n = e.data[e.index] = Array(t), a = 0; a < t; a++)
        n[a] = Ta;
    return e.index++, n;
  }
  function jn(t, e) {
    return typeof e == "function" ? e(t) : e;
  }
  function Ps(t) {
    var e = Xt();
    return Tr(e, Rt, t);
  }
  function Tr(t, e, n) {
    var a = t.queue;
    if (a === null) throw Error(o(311));
    a.lastRenderedReducer = n;
    var s = t.baseQueue, u = a.pending;
    if (u !== null) {
      if (s !== null) {
        var f = s.next;
        s.next = u.next, u.next = f;
      }
      e.baseQueue = s = u, a.pending = null;
    }
    if (u = t.baseState, s === null) t.memoizedState = u;
    else {
      e = s.next;
      var m = f = null, S = null, D = e, N = !1;
      do {
        var w = D.lane & -536870913;
        if (w !== D.lane ? (yt & w) === w : (Vn & w) === w) {
          var A = D.revertLane;
          if (A === 0)
            S !== null && (S = S.next = {
              lane: 0,
              revertLane: 0,
              gesture: null,
              action: D.action,
              hasEagerState: D.hasEagerState,
              eagerState: D.eagerState,
              next: null
            }), w === wa && (N = !0);
          else if ((Vn & A) === A) {
            D = D.next, A === wa && (N = !0);
            continue;
          } else
            w = {
              lane: 0,
              revertLane: D.revertLane,
              gesture: null,
              action: D.action,
              hasEagerState: D.hasEagerState,
              eagerState: D.eagerState,
              next: null
            }, S === null ? (m = S = w, f = u) : S = S.next = w, ut.lanes |= A, sa |= A;
          w = D.action, Ha && n(u, w), u = D.hasEagerState ? D.eagerState : n(u, w);
        } else
          A = {
            lane: w,
            revertLane: D.revertLane,
            gesture: D.gesture,
            action: D.action,
            hasEagerState: D.hasEagerState,
            eagerState: D.eagerState,
            next: null
          }, S === null ? (m = S = A, f = u) : S = S.next = A, ut.lanes |= w, sa |= w;
        D = D.next;
      } while (D !== null && D !== e);
      if (S === null ? f = u : S.next = m, !Re(u, t.memoizedState) && (Kt = !0, N && (n = pi, n !== null)))
        throw n;
      t.memoizedState = u, t.baseState = f, t.baseQueue = S, a.lastRenderedState = u;
    }
    return s === null && (a.lanes = 0), [t.memoizedState, a.dispatch];
  }
  function xr(t) {
    var e = Xt(), n = e.queue;
    if (n === null) throw Error(o(311));
    n.lastRenderedReducer = t;
    var a = n.dispatch, s = n.pending, u = e.memoizedState;
    if (s !== null) {
      n.pending = null;
      var f = s = s.next;
      do
        u = t(u, f.action), f = f.next;
      while (f !== s);
      Re(u, e.memoizedState) || (Kt = !0), e.memoizedState = u, e.baseQueue === null && (e.baseState = u), n.lastRenderedState = u;
    }
    return [u, a];
  }
  function Pd(t, e, n) {
    var a = ut, s = Xt(), u = ft;
    if (u) {
      if (n === void 0) throw Error(o(407));
      n = n();
    } else n = e();
    var f = !Re(
      (Rt || s).memoizedState,
      n
    );
    if (f && (s.memoizedState = n, Kt = !0), s = s.queue, Mr(Id.bind(null, a, s, t), [
      t
    ]), t = s.getSnapshot !== e || f || Zt !== null && (Zt.memoizedState.tag & 1) !== 0, Ti(
      t ? 9 : 8,
      { destroy: void 0 },
      Wd.bind(null, a, s, n, e),
      null
    ), t) {
      if (a.flags |= 2048, _t === null) throw Error(o(349));
      u || (Vn & 127) !== 0 || Fd(a, e, n);
    }
    return n;
  }
  function Fd(t, e, n) {
    t.flags |= 16384, t = { getSnapshot: e, value: n }, e = ut.updateQueue, e === null ? (e = Js(), ut.updateQueue = e, e.stores = [t]) : (n = e.stores, n === null ? e.stores = [t] : n.push(t));
  }
  function Wd(t, e, n, a) {
    e.value = n, e.getSnapshot = a, $d(e) && tm(t);
  }
  function Id(t, e, n) {
    return n(function() {
      $d(e) && tm(t);
    });
  }
  function $d(t) {
    var e = t.getSnapshot;
    t = t.value;
    try {
      var n = e();
      return !Re(t, n);
    } catch {
      return !0;
    }
  }
  function tm(t) {
    var e = Ca(t, 2);
    e !== null && De(e, t, 2);
  }
  function Er(t) {
    var e = pe();
    if (typeof t == "function") {
      var n = t;
      if (t = n(), Ha) {
        Xn(!0);
        try {
          n();
        } finally {
          Xn(!1);
        }
      }
    }
    return e.memoizedState = e.baseState = t, e.queue = {
      pending: null,
      lanes: 0,
      dispatch: null,
      lastRenderedReducer: jn,
      lastRenderedState: t
    }, e;
  }
  function em(t, e, n, a) {
    return t.baseState = n, Tr(
      t,
      Rt,
      typeof a == "function" ? a : jn
    );
  }
  function Ab(t, e, n, a, s) {
    if (Is(t)) throw Error(o(485));
    if (t = e.action, t !== null) {
      var u = {
        payload: s,
        action: t,
        next: null,
        isTransition: !0,
        status: "pending",
        value: null,
        reason: null,
        listeners: [],
        then: function(f) {
          u.listeners.push(f);
        }
      };
      W.T !== null ? n(!0) : u.isTransition = !1, a(u), n = e.pending, n === null ? (u.next = e.pending = u, nm(e, u)) : (u.next = n.next, e.pending = n.next = u);
    }
  }
  function nm(t, e) {
    var n = e.action, a = e.payload, s = t.state;
    if (e.isTransition) {
      var u = W.T, f = {};
      f.types = u !== null ? u.types : null, W.T = f;
      try {
        var m = n(s, a), S = W.S;
        S !== null && S(f, m), am(t, e, m);
      } catch (D) {
        Ar(t, e, D);
      } finally {
        u !== null && f.types !== null && (u.types = f.types), W.T = u;
      }
    } else
      try {
        u = n(s, a), am(t, e, u);
      } catch (D) {
        Ar(t, e, D);
      }
  }
  function am(t, e, n) {
    n !== null && typeof n == "object" && typeof n.then == "function" ? n.then(
      function(a) {
        im(t, e, a);
      },
      function(a) {
        return Ar(t, e, a);
      }
    ) : im(t, e, n);
  }
  function im(t, e, n) {
    e.status = "fulfilled", e.value = n, lm(e), t.state = n, e = t.pending, e !== null && (n = e.next, n === e ? t.pending = null : (n = n.next, e.next = n, nm(t, n)));
  }
  function Ar(t, e, n) {
    var a = t.pending;
    if (t.pending = null, a !== null) {
      a = a.next;
      do
        e.status = "rejected", e.reason = n, lm(e), e = e.next;
      while (e !== a);
    }
    t.action = null;
  }
  function lm(t) {
    t = t.listeners;
    for (var e = 0; e < t.length; e++) (0, t[e])();
  }
  function sm(t, e) {
    return e;
  }
  function um(t, e) {
    if (ft) {
      var n = _t.formState;
      if (n !== null) {
        t: {
          var a = ut;
          if (ft) {
            if (Ut) {
              e: {
                for (var s = Ut, u = Qe; s.nodeType !== 8; ) {
                  if (!u) {
                    s = null;
                    break e;
                  }
                  if (s = Ke(
                    s.nextSibling
                  ), s === null) {
                    s = null;
                    break e;
                  }
                }
                u = s.data, s = u === "F!" || u === "F" ? s : null;
              }
              if (s) {
                Ut = Ke(
                  s.nextSibling
                ), a = s.data === "F!";
                break t;
              }
            }
            kn(a);
          }
          a = !1;
        }
        a && (e = n[0]);
      }
    }
    return n = pe(), n.memoizedState = n.baseState = e, a = {
      pending: null,
      lanes: 0,
      dispatch: null,
      lastRenderedReducer: sm,
      lastRenderedState: e
    }, n.queue = a, n = Dm.bind(
      null,
      ut,
      a
    ), a.dispatch = n, a = Er(!1), u = zr.bind(
      null,
      ut,
      !1,
      a.queue
    ), a = pe(), s = {
      state: e,
      dispatch: null,
      action: t,
      pending: null
    }, a.queue = s, n = Ab.bind(
      null,
      ut,
      s,
      u,
      n
    ), s.dispatch = n, a.memoizedState = t, [e, n, !1];
  }
  function om(t) {
    var e = Xt();
    return rm(e, Rt, t);
  }
  function rm(t, e, n) {
    if (e = Tr(
      t,
      e,
      sm
    )[0], t = Ps(jn)[0], typeof e == "object" && e !== null && typeof e.then == "function")
      try {
        var a = Al(e);
      } catch (f) {
        throw f === gi ? Ls : f;
      }
    else a = e;
    e = Xt();
    var s = e.queue, u = s.dispatch;
    return n !== e.memoizedState && (ut.flags |= 2048, Ti(
      9,
      { destroy: void 0 },
      Mb.bind(null, s, n),
      null
    )), [a, u, t];
  }
  function Mb(t, e) {
    t.action = e;
  }
  function cm(t) {
    var e = Xt(), n = Rt;
    if (n !== null)
      return rm(e, n, t);
    Xt(), e = e.memoizedState, n = Xt();
    var a = n.queue.dispatch;
    return n.memoizedState = t, [e, a, !1];
  }
  function Ti(t, e, n, a) {
    return t = { tag: t, create: n, deps: a, inst: e, next: null }, e = ut.updateQueue, e === null && (e = Js(), ut.updateQueue = e), n = e.lastEffect, n === null ? e.lastEffect = t.next = t : (a = n.next, n.next = t, t.next = a, e.lastEffect = t), t;
  }
  function fm() {
    return Xt().memoizedState;
  }
  function Fs(t, e, n, a) {
    var s = pe();
    ut.flags |= t, s.memoizedState = Ti(
      1 | e,
      { destroy: void 0 },
      n,
      a === void 0 ? null : a
    );
  }
  function Ws(t, e, n, a) {
    var s = Xt();
    a = a === void 0 ? null : a;
    var u = s.memoizedState.inst;
    Rt !== null && a !== null && yr(a, Rt.memoizedState.deps) ? s.memoizedState = Ti(e, u, n, a) : (ut.flags |= t, s.memoizedState = Ti(
      1 | e,
      u,
      n,
      a
    ));
  }
  function hm(t, e) {
    Fs(8390656, 8, t, e);
  }
  function Mr(t, e) {
    Ws(2048, 8, t, e);
  }
  function Db(t) {
    ut.flags |= 4;
    var e = ut.updateQueue;
    if (e === null)
      e = Js(), ut.updateQueue = e, e.events = [t];
    else {
      var n = e.events;
      n === null ? e.events = [t] : n.push(t);
    }
  }
  function dm(t) {
    var e = Xt().memoizedState;
    return Db({ ref: e, nextImpl: t }), function() {
      if ((Et & 2) !== 0) throw Error(o(440));
      return e.impl.apply(void 0, arguments);
    };
  }
  function mm(t, e) {
    return Ws(4, 2, t, e);
  }
  function ym(t, e) {
    return Ws(4, 4, t, e);
  }
  function pm(t, e) {
    if (typeof e == "function") {
      t = t();
      var n = e(t);
      return function() {
        typeof n == "function" ? n() : e(null);
      };
    }
    if (e != null)
      return t = t(), e.current = t, function() {
        e.current = null;
      };
  }
  function gm(t, e, n) {
    n = n != null ? n.concat([t]) : null, Ws(4, 4, pm.bind(null, e, t), n);
  }
  function Dr() {
  }
  function vm(t, e) {
    var n = Xt();
    e = e === void 0 ? null : e;
    var a = n.memoizedState;
    return e !== null && yr(e, a[1]) ? a[0] : (n.memoizedState = [t, e], t);
  }
  function bm(t, e) {
    var n = Xt();
    e = e === void 0 ? null : e;
    var a = n.memoizedState;
    if (e !== null && yr(e, a[1]))
      return a[0];
    if (a = t(), Ha) {
      Xn(!0);
      try {
        t();
      } finally {
        Xn(!1);
      }
    }
    return n.memoizedState = [a, e], a;
  }
  function Cr(t, e, n) {
    return n === void 0 || (Vn & 1073741824) !== 0 && (yt & 261930) === 0 ? t.memoizedState = e : (t.memoizedState = n, t = Ny(), ut.lanes |= t, sa |= t, n);
  }
  function Sm(t, e, n, a) {
    return Re(n, e) ? n : ta.current !== null ? (t = Cr(t, n, a), Re(t, e) || (Kt = !0), t) : (Vn & 106) === 0 || (Vn & 1073741824) !== 0 && (yt & 261930) === 0 ? (Kt = !0, t.memoizedState = n) : (t = Ny(), ut.lanes |= t, sa |= t, e);
  }
  function Tm(t, e, n, a, s) {
    var u = lt.p;
    lt.p = u !== 0 && 8 > u ? u : 8;
    var f = W.T, m = {};
    m.types = f !== null ? f.types : null, W.T = m, zr(t, !1, e, n);
    try {
      var S = s(), D = W.S;
      if (D !== null && D(m, S), S !== null && typeof S == "object" && typeof S.then == "function") {
        var N = Tb(
          S,
          a
        );
        Ml(
          t,
          e,
          N,
          Ue(t)
        );
      } else
        Ml(
          t,
          e,
          a,
          Ue(t)
        );
    } catch (w) {
      Ml(
        t,
        e,
        { then: function() {
        }, status: "rejected", reason: w },
        Ue()
      );
    } finally {
      lt.p = u, f !== null && m.types !== null && (f.types = m.types), W.T = f;
    }
  }
  function Cb() {
  }
  function Or(t, e, n, a) {
    if (t.tag !== 5) throw Error(o(476));
    var s = xm(t).queue;
    Tm(
      t,
      s,
      e,
      An,
      n === null ? Cb : function() {
        return Em(t), n(a);
      }
    );
  }
  function xm(t) {
    var e = t.memoizedState;
    if (e !== null) return e;
    e = {
      memoizedState: An,
      baseState: An,
      baseQueue: null,
      queue: {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: jn,
        lastRenderedState: An
      },
      next: null
    };
    var n = {};
    return e.next = {
      memoizedState: n,
      baseState: n,
      baseQueue: null,
      queue: {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: jn,
        lastRenderedState: n
      },
      next: null
    }, t.memoizedState = e, t = t.alternate, t !== null && (t.memoizedState = e), e;
  }
  function Em(t) {
    var e = xm(t);
    e.next === null && (e = t.alternate.memoizedState), Ml(
      t,
      e.next.queue,
      {},
      Ue()
    );
  }
  function Nr() {
    return le(Yi);
  }
  function Am() {
    return Xt().memoizedState;
  }
  function Mm() {
    return Xt().memoizedState;
  }
  function Ob(t) {
    for (var e = t.return; e !== null; ) {
      switch (e.tag) {
        case 24:
        case 3:
          var n = Ue();
          t = In(n);
          var a = $n(e, t, n);
          a !== null && (De(a, e, n), bl(a, e, n)), e = { cache: ar() }, t.payload = e;
          return;
      }
      e = e.return;
    }
  }
  function Nb(t, e, n) {
    var a = Ue();
    n = {
      lane: a,
      revertLane: 0,
      gesture: null,
      action: n,
      hasEagerState: !1,
      eagerState: null,
      next: null
    }, Is(t) ? Cm(e, n) : (n = ko(t, e, n, a), n !== null && (De(n, t, a), Om(n, e, a)));
  }
  function Dm(t, e, n) {
    var a = Ue();
    Ml(t, e, n, a);
  }
  function Ml(t, e, n, a) {
    var s = {
      lane: a,
      revertLane: 0,
      gesture: null,
      action: n,
      hasEagerState: !1,
      eagerState: null,
      next: null
    };
    if (Is(t)) Cm(e, s);
    else {
      var u = t.alternate;
      if (t.lanes === 0 && (u === null || u.lanes === 0) && (u = e.lastRenderedReducer, u !== null))
        try {
          var f = e.lastRenderedState, m = u(f, n);
          if (s.hasEagerState = !0, s.eagerState = m, Re(m, f))
            return Ns(t, e, s, 0), _t === null && Os(), !1;
        } catch {
        }
      if (n = ko(t, e, s, a), n !== null)
        return De(n, t, a), Om(n, e, a), !0;
    }
    return !1;
  }
  function zr(t, e, n, a) {
    if (a = {
      lane: 2,
      revertLane: Sc(),
      gesture: null,
      action: a,
      hasEagerState: !1,
      eagerState: null,
      next: null
    }, Is(t)) {
      if (e) throw Error(o(479));
    } else
      e = ko(
        t,
        n,
        a,
        2
      ), e !== null && De(e, t, 2);
  }
  function Is(t) {
    var e = t.alternate;
    return t === ut || e !== null && e === ut;
  }
  function Cm(t, e) {
    bi = Zs = !0;
    var n = t.pending;
    n === null ? e.next = e : (e.next = n.next, n.next = e), t.pending = e;
  }
  function Om(t, e, n) {
    if ((n & 4194048) !== 0) {
      var a = e.lanes;
      a &= t.pendingLanes, n |= a, e.lanes = n, Nh(t, n);
    }
  }
  var $s = {
    readContext: le,
    use: ks,
    useCallback: Yt,
    useContext: Yt,
    useEffect: Yt,
    useImperativeHandle: Yt,
    useLayoutEffect: Yt,
    useInsertionEffect: Yt,
    useMemo: Yt,
    useReducer: Yt,
    useRef: Yt,
    useState: Yt,
    useDebugValue: Yt,
    useDeferredValue: Yt,
    useTransition: Yt,
    useSyncExternalStore: Yt,
    useId: Yt,
    useHostTransitionStatus: Yt,
    useFormState: Yt,
    useActionState: Yt,
    useOptimistic: Yt,
    useMemoCache: Yt,
    useCacheRefresh: Yt,
    useEffectEvent: Yt
  }, Nm = {
    readContext: le,
    use: ks,
    useCallback: function(t, e) {
      return pe().memoizedState = [
        t,
        e === void 0 ? null : e
      ], t;
    },
    useContext: le,
    useEffect: hm,
    useImperativeHandle: function(t, e, n) {
      n = n != null ? n.concat([t]) : null, Fs(
        4194308,
        4,
        pm.bind(null, e, t),
        n
      );
    },
    useLayoutEffect: function(t, e) {
      return Fs(4194308, 4, t, e);
    },
    useInsertionEffect: function(t, e) {
      Fs(4, 2, t, e);
    },
    useMemo: function(t, e) {
      var n = pe();
      e = e === void 0 ? null : e;
      var a = t();
      if (Ha) {
        Xn(!0);
        try {
          t();
        } finally {
          Xn(!1);
        }
      }
      return n.memoizedState = [a, e], a;
    },
    useReducer: function(t, e, n) {
      var a = pe();
      if (n !== void 0) {
        var s = n(e);
        if (Ha) {
          Xn(!0);
          try {
            n(e);
          } finally {
            Xn(!1);
          }
        }
      } else s = e;
      return a.memoizedState = a.baseState = s, t = {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: t,
        lastRenderedState: s
      }, a.queue = t, t = t.dispatch = Nb.bind(
        null,
        ut,
        t
      ), [a.memoizedState, t];
    },
    useRef: function(t) {
      var e = pe();
      return t = { current: t }, e.memoizedState = t;
    },
    useState: function(t) {
      t = Er(t);
      var e = t.queue, n = Dm.bind(null, ut, e);
      return e.dispatch = n, [t.memoizedState, n];
    },
    useDebugValue: Dr,
    useDeferredValue: function(t, e) {
      var n = pe();
      return Cr(n, t, e);
    },
    useTransition: function() {
      var t = Er(!1);
      return t = Tm.bind(
        null,
        ut,
        t.queue,
        !0,
        !1
      ), pe().memoizedState = t, [!1, t];
    },
    useSyncExternalStore: function(t, e, n) {
      var a = ut, s = pe();
      if (ft) {
        if (n === void 0)
          throw Error(o(407));
        n = n();
      } else {
        if (n = e(), _t === null)
          throw Error(o(349));
        (yt & 127) !== 0 || Fd(a, e, n);
      }
      s.memoizedState = n;
      var u = { value: n, getSnapshot: e };
      return s.queue = u, hm(Id.bind(null, a, u, t), [
        t
      ]), a.flags |= 2048, Ti(
        9,
        { destroy: void 0 },
        Wd.bind(
          null,
          a,
          u,
          n,
          e
        ),
        null
      ), n;
    },
    useId: function() {
      var t = pe(), e = _t.identifierPrefix;
      if (ft) {
        var n = fn, a = cn;
        n = (a & ~(1 << 32 - Ne(a) - 1)).toString(32) + n, e = "_" + e + "R_" + n, n = Ks++, 0 < n && (e += "H" + n.toString(32)), e += "_";
      } else
        n = xb++, e = "_" + e + "r_" + n.toString(32) + "_";
      return t.memoizedState = e;
    },
    useHostTransitionStatus: Nr,
    useFormState: um,
    useActionState: um,
    useOptimistic: function(t) {
      var e = pe();
      e.memoizedState = e.baseState = t;
      var n = {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: null,
        lastRenderedState: null
      };
      return e.queue = n, e = zr.bind(
        null,
        ut,
        !0,
        n
      ), n.dispatch = e, [t, e];
    },
    useMemoCache: Sr,
    useCacheRefresh: function() {
      return pe().memoizedState = Ob.bind(
        null,
        ut
      );
    },
    useEffectEvent: function(t) {
      var e = pe(), n = { impl: t };
      return e.memoizedState = n, function() {
        if ((Et & 2) !== 0)
          throw Error(o(440));
        return n.impl.apply(void 0, arguments);
      };
    }
  }, zm = {
    readContext: le,
    use: ks,
    useCallback: vm,
    useContext: le,
    useEffect: Mr,
    useImperativeHandle: gm,
    useInsertionEffect: mm,
    useLayoutEffect: ym,
    useMemo: bm,
    useReducer: Ps,
    useRef: fm,
    useState: function() {
      return Ps(jn);
    },
    useDebugValue: Dr,
    useDeferredValue: function(t, e) {
      var n = Xt();
      return Sm(
        n,
        Rt.memoizedState,
        t,
        e
      );
    },
    useTransition: function() {
      var t = Ps(jn)[0], e = Xt().memoizedState;
      return [
        typeof t == "boolean" ? t : Al(t),
        e
      ];
    },
    useSyncExternalStore: Pd,
    useId: Am,
    useHostTransitionStatus: Nr,
    useFormState: om,
    useActionState: om,
    useOptimistic: function(t, e) {
      var n = Xt();
      return em(n, Rt, t, e);
    },
    useMemoCache: Sr,
    useCacheRefresh: Mm,
    useEffectEvent: dm
  }, zb = {
    readContext: le,
    use: ks,
    useCallback: vm,
    useContext: le,
    useEffect: Mr,
    useImperativeHandle: gm,
    useInsertionEffect: mm,
    useLayoutEffect: ym,
    useMemo: bm,
    useReducer: xr,
    useRef: fm,
    useState: function() {
      return xr(jn);
    },
    useDebugValue: Dr,
    useDeferredValue: function(t, e) {
      var n = Xt();
      return Rt === null ? Cr(n, t, e) : Sm(
        n,
        Rt.memoizedState,
        t,
        e
      );
    },
    useTransition: function() {
      var t = xr(jn)[0], e = Xt().memoizedState;
      return [
        typeof t == "boolean" ? t : Al(t),
        e
      ];
    },
    useSyncExternalStore: Pd,
    useId: Am,
    useHostTransitionStatus: Nr,
    useFormState: cm,
    useActionState: cm,
    useOptimistic: function(t, e) {
      var n = Xt();
      return Rt !== null ? em(n, Rt, t, e) : (n.baseState = t, [t, n.queue.dispatch]);
    },
    useMemoCache: Sr,
    useCacheRefresh: Mm,
    useEffectEvent: dm
  };
  function Rr(t, e, n, a) {
    e = t.memoizedState, n = n(a, e), n = n == null ? e : J({}, e, n), t.memoizedState = n, t.lanes === 0 && (t.updateQueue.baseState = n);
  }
  var _r = {
    enqueueSetState: function(t, e, n) {
      t = t._reactInternals;
      var a = Ue(), s = In(a);
      s.payload = e, n != null && (s.callback = n), e = $n(t, s, a), e !== null && (De(e, t, a), bl(e, t, a));
    },
    enqueueReplaceState: function(t, e, n) {
      t = t._reactInternals;
      var a = Ue(), s = In(a);
      s.tag = 1, s.payload = e, n != null && (s.callback = n), e = $n(t, s, a), e !== null && (De(e, t, a), bl(e, t, a));
    },
    enqueueForceUpdate: function(t, e) {
      t = t._reactInternals;
      var n = Ue(), a = In(n);
      a.tag = 2, e != null && (a.callback = e), e = $n(t, a, n), e !== null && (De(e, t, n), bl(e, t, n));
    }
  };
  function Rm(t, e, n, a, s, u, f) {
    return t = t.stateNode, typeof t.shouldComponentUpdate == "function" ? t.shouldComponentUpdate(a, u, f) : e.prototype && e.prototype.isPureReactComponent ? !fl(n, a) || !fl(s, u) : !0;
  }
  function _m(t, e, n, a) {
    t = e.state, typeof e.componentWillReceiveProps == "function" && e.componentWillReceiveProps(n, a), typeof e.UNSAFE_componentWillReceiveProps == "function" && e.UNSAFE_componentWillReceiveProps(n, a), e.state !== t && _r.enqueueReplaceState(e, e.state, null);
  }
  function La(t, e) {
    var n = e;
    if ("ref" in e) {
      n = {};
      for (var a in e)
        a !== "ref" && (n[a] = e[a]);
    }
    if (t = t.defaultProps) {
      n === e && (n = J({}, n));
      for (var s in t)
        n[s] === void 0 && (n[s] = t[s]);
    }
    return n;
  }
  function wm(t) {
    Cs(t);
  }
  function Vm(t) {
    console.error(t);
  }
  function jm(t) {
    Cs(t);
  }
  function tu(t, e) {
    try {
      var n = t.onUncaughtError;
      n(e.value, { componentStack: e.stack });
    } catch (a) {
      setTimeout(function() {
        throw a;
      });
    }
  }
  function Um(t, e, n) {
    try {
      var a = t.onCaughtError;
      a(n.value, {
        componentStack: n.stack,
        errorBoundary: e.tag === 1 ? e.stateNode : null
      });
    } catch (s) {
      setTimeout(function() {
        throw s;
      });
    }
  }
  function wr(t, e, n) {
    return n = In(n), n.tag = 3, n.payload = { element: null }, n.callback = function() {
      tu(t, e);
    }, n;
  }
  function Bm(t) {
    return t = In(t), t.tag = 3, t;
  }
  function Hm(t, e, n, a) {
    var s = n.type.getDerivedStateFromError;
    if (typeof s == "function") {
      var u = a.value;
      t.payload = function() {
        return s(u);
      }, t.callback = function() {
        Um(e, n, a);
      };
    }
    var f = n.stateNode;
    f !== null && typeof f.componentDidCatch == "function" && (t.callback = function() {
      Um(e, n, a), typeof s != "function" && (ua === null ? ua = /* @__PURE__ */ new Set([this]) : ua.add(this));
      var m = a.stack;
      this.componentDidCatch(a.value, {
        componentStack: m !== null ? m : ""
      });
    });
  }
  function Rb(t, e, n, a, s) {
    if (n.flags |= 32768, a !== null && typeof a == "object" && typeof a.then == "function") {
      if (e = n.alternate, e !== null && Ra(
        e,
        n,
        s,
        !0
      ), n = se.current, n !== null) {
        switch (n.tag) {
          case 31:
          case 13:
          case 19:
            return me === null ? Tu() : n.alternate === null && qt === 0 && (qt = 3), n.flags &= -257, n.flags |= 65536, n.lanes = s, a === Ys ? n.flags |= 16384 : (e = n.updateQueue, e === null ? n.updateQueue = /* @__PURE__ */ new Set([a]) : e.add(a), gc(t, a, s)), !1;
          case 22:
            return n.flags |= 65536, a === Ys ? n.flags |= 16384 : (e = n.updateQueue, e === null ? (e = {
              transitions: null,
              markerInstances: null,
              retryQueue: /* @__PURE__ */ new Set([a])
            }, n.updateQueue = e) : (n = e.retryQueue, n === null ? e.retryQueue = /* @__PURE__ */ new Set([a]) : n.add(a)), gc(t, a, s)), !1;
        }
        throw Error(o(435, n.tag));
      }
      return gc(t, a, s), Tu(), !1;
    }
    if (ft)
      return e = se.current, e !== null ? ((e.flags & 65536) === 0 && (e.flags |= 256), e.flags |= 65536, e.lanes = s, a !== $o && (t = Error(o(422), { cause: a }), ml(qe(t, n)))) : (a !== $o && (e = Error(o(423), {
        cause: a
      }), ml(
        qe(e, n)
      )), t = t.current.alternate, t.flags |= 65536, s &= -s, t.lanes |= s, a = qe(a, n), s = wr(
        t.stateNode,
        a,
        s
      ), rr(t, s), qt !== 4 && (qt = 2)), !1;
    var u = Error(o(520), { cause: a });
    if (u = qe(u, n), wl === null ? wl = [u] : wl.push(u), qt !== 4 && (qt = 2), e === null) return !0;
    a = qe(a, n), n = e;
    do {
      switch (n.tag) {
        case 3:
          return n.flags |= 65536, t = s & -s, n.lanes |= t, t = wr(n.stateNode, a, t), rr(n, t), !1;
        case 1:
          if (e = n.type, u = n.stateNode, (n.flags & 128) === 0 && (typeof e.getDerivedStateFromError == "function" || u !== null && typeof u.componentDidCatch == "function" && (ua === null || !ua.has(u))))
            return n.flags |= 65536, s &= -s, n.lanes |= s, s = Bm(s), Hm(
              s,
              t,
              n,
              a
            ), rr(n, s), !1;
          break;
        case 22:
          if (n.memoizedState !== null)
            return n.flags |= 65536, !1;
      }
      n = n.return;
    } while (n !== null);
    return !1;
  }
  var Vr = Error(o(461)), Kt = !1;
  function Pt(t, e, n, a) {
    e.child = t === null ? Gd(e, null, n, a) : Ba(
      e,
      t.child,
      n,
      a
    );
  }
  function Lm(t, e, n, a, s) {
    n = n.render;
    var u = e.ref;
    if ("ref" in a) {
      var f = {};
      for (var m in a)
        m !== "ref" && (f[m] = a[m]);
    } else f = a;
    return _a(e), a = pr(
      t,
      e,
      n,
      f,
      u,
      s
    ), m = gr(), t !== null && !Kt ? (vr(t, e, s), Un(t, e, s)) : (ft && m && ws(e), e.flags |= 1, Pt(t, e, a, s), e.child);
  }
  function Ym(t, e, n, a, s) {
    if (t === null) {
      var u = n.type;
      return typeof u == "function" && !Po(u) && u.defaultProps === void 0 && n.compare === null ? (e.tag = 15, e.type = u, qm(
        t,
        e,
        u,
        a,
        s
      )) : (t = Rs(
        n.type,
        null,
        a,
        e,
        e.mode,
        s
      ), t.ref = e.ref, t.return = e, e.child = t);
    }
    if (u = t.child, !Gr(t, s)) {
      var f = u.memoizedProps;
      if (n = n.compare, n = n !== null ? n : fl, n(f, a) && t.ref === e.ref)
        return Un(t, e, s);
    }
    return e.flags |= 1, t = zn(u, a), t.ref = e.ref, t.return = e, e.child = t;
  }
  function qm(t, e, n, a, s) {
    if (t !== null) {
      var u = t.memoizedProps;
      if (fl(u, a) && t.ref === e.ref)
        if (Kt = !1, e.pendingProps = a = u, Gr(t, s))
          (t.flags & 131072) !== 0 && (Kt = !0);
        else
          return e.lanes = t.lanes, Un(t, e, s);
    }
    return jr(
      t,
      e,
      n,
      a,
      s
    );
  }
  function Gm(t, e, n, a) {
    var s = a.children, u = t !== null ? t.memoizedState : null;
    if (t === null && e.stateNode === null && (e.stateNode = {
      _visibility: 1,
      _pendingMarkers: null,
      _retryCache: null,
      _transitions: null
    }), a.mode === "hidden") {
      if ((e.flags & 128) !== 0) {
        if (u = u !== null ? u.baseLanes | n : n, t !== null) {
          for (a = e.child = t.child, s = 0; a !== null; )
            s = s | a.lanes | a.childLanes, a = a.sibling;
          a = s & ~u;
        } else a = 0, e.child = null;
        return Xm(
          t,
          e,
          u,
          n,
          a
        );
      }
      if ((n & 536870912) !== 0)
        e.memoizedState = { baseLanes: 0, cachePool: null }, t !== null && Hs(
          e,
          u !== null ? u.cachePool : null
        ), u !== null ? Zd(e, u) : fr(), Kd(e);
      else
        return a = e.lanes = 536870912, Xm(
          t,
          e,
          u !== null ? u.baseLanes | n : n,
          n,
          a
        );
    } else
      u !== null ? (Hs(e, u.cachePool), Zd(e, u), na(), e.memoizedState = null) : (t !== null && Hs(e, null), fr(), na());
    return Pt(t, e, s, n), e.child;
  }
  function Dl(t, e) {
    return t !== null && t.tag === 22 || e.stateNode !== null || (e.stateNode = {
      _visibility: 1,
      _pendingMarkers: null,
      _retryCache: null,
      _transitions: null
    }), e.sibling;
  }
  function Xm(t, e, n, a, s) {
    var u = lr();
    return u = u === null ? null : { parent: Qt._currentValue, pool: u }, e.memoizedState = {
      baseLanes: n,
      cachePool: u
    }, t !== null && Hs(e, null), fr(), Kd(e), t !== null && Ra(t, e, a, !0), e.childLanes = s, null;
  }
  function eu(t, e) {
    return e = nu(
      { mode: e.mode, children: e.children },
      t.mode
    ), e.ref = t.ref, t.child = e, e.return = t, e;
  }
  function Qm(t, e, n) {
    return Ba(e, t.child, null, n), t = eu(e, e.pendingProps), t.flags |= 2, _e(e), e.memoizedState = null, t;
  }
  function _b(t, e, n) {
    var a = e.pendingProps, s = (e.flags & 128) !== 0;
    if (e.flags &= -129, t === null) {
      if (ft) {
        if (a.mode === "hidden")
          return t = eu(e, a), e.lanes = 536870912, t.memoizedState = { baseLanes: 0, cachePool: null }, Dl(null, t);
        if (dr(e), (t = Ut) ? (t = pp(
          t,
          Qe
        ), t = t !== null && t.data === "&" ? t : null, t !== null && (e.memoizedState = {
          dehydrated: t,
          treeContext: Kn !== null ? { id: cn, overflow: fn } : null,
          retryLane: 536870912,
          hydrationErrors: null
        }, n = Cd(t), n.return = e, e.child = n, te = e, Ut = null)) : t = null, t === null) throw kn(e);
        return e.lanes = 536870912, null;
      }
      return eu(e, a);
    }
    var u = t.memoizedState;
    if (u !== null) {
      var f = u.dehydrated;
      if (dr(e), s)
        if (e.flags & 256)
          e.flags &= -257, e = Qm(
            t,
            e,
            n
          );
        else if (e.memoizedState !== null)
          e.child = t.child, e.flags |= 128, e = null;
        else throw Error(o(558));
      else if (Kt || Ra(t, e, n, !1), s = (n & t.childLanes) !== 0, Kt || s) {
        if (ta.current === null) {
          if (a = _t, a !== null && (f = zh(a, n), f !== 0 && f !== u.retryLane))
            throw u.retryLane = f, Ca(t, f), De(a, t, f), Vr;
          Tu();
        }
        e = Qm(
          t,
          e,
          n
        );
      } else
        t = u.treeContext, Ut = Ke(f.nextSibling), te = e, ft = !0, Jn = null, Qe = !1, t !== null && zd(e, t), e = eu(e, a), e.flags |= 134221824;
      return e;
    }
    return t = zn(t.child, {
      mode: a.mode,
      children: a.children
    }), t.ref = e.ref, e.child = t, t.return = e, t;
  }
  function xi(t, e) {
    var n = e.ref;
    if (n === null)
      t !== null && t.ref !== null && (e.flags |= 4194816);
    else {
      if (typeof n != "function" && typeof n != "object")
        throw Error(o(284));
      (t === null || t.ref !== n) && (e.flags |= 4194816);
    }
  }
  function jr(t, e, n, a, s) {
    return _a(e), n = pr(
      t,
      e,
      n,
      a,
      void 0,
      s
    ), a = gr(), t !== null && !Kt ? (vr(t, e, s), Un(t, e, s)) : (ft && a && ws(e), e.flags |= 1, Pt(t, e, n, s), e.child);
  }
  function Zm(t, e, n, a, s, u) {
    return _a(e), e.updateQueue = null, n = kd(
      e,
      a,
      n,
      s
    ), Jd(t), a = gr(), t !== null && !Kt ? (vr(t, e, u), Un(t, e, u)) : (ft && a && ws(e), e.flags |= 1, Pt(t, e, n, u), e.child);
  }
  function Km(t, e, n, a, s) {
    if (_a(e), e.stateNode === null) {
      var u = hi, f = n.contextType;
      typeof f == "object" && f !== null && (u = le(f)), u = new n(a, u), e.memoizedState = u.state !== null && u.state !== void 0 ? u.state : null, u.updater = _r, e.stateNode = u, u._reactInternals = e, u = e.stateNode, u.props = a, u.state = e.memoizedState, u.refs = {}, ur(e), f = n.contextType, u.context = typeof f == "object" && f !== null ? le(f) : hi, u.state = e.memoizedState, f = n.getDerivedStateFromProps, typeof f == "function" && (Rr(
        e,
        n,
        f,
        a
      ), u.state = e.memoizedState), typeof n.getDerivedStateFromProps == "function" || typeof u.getSnapshotBeforeUpdate == "function" || typeof u.UNSAFE_componentWillMount != "function" && typeof u.componentWillMount != "function" || (f = u.state, typeof u.componentWillMount == "function" && u.componentWillMount(), typeof u.UNSAFE_componentWillMount == "function" && u.UNSAFE_componentWillMount(), f !== u.state && _r.enqueueReplaceState(u, u.state, null), Tl(e, a, u, s), Sl(), u.state = e.memoizedState), typeof u.componentDidMount == "function" && (e.flags |= 4194308), a = !0;
    } else if (t === null) {
      u = e.stateNode;
      var m = e.memoizedProps, S = La(n, m);
      u.props = S;
      var D = u.context, N = n.contextType;
      f = hi, typeof N == "object" && N !== null && (f = le(N));
      var w = n.getDerivedStateFromProps;
      N = typeof w == "function" || typeof u.getSnapshotBeforeUpdate == "function", m = e.pendingProps !== m, N || typeof u.UNSAFE_componentWillReceiveProps != "function" && typeof u.componentWillReceiveProps != "function" || (m || D !== f) && _m(
        e,
        u,
        a,
        f
      ), Wn = !1;
      var A = e.memoizedState;
      u.state = A, Tl(e, a, u, s), Sl(), D = e.memoizedState, m || A !== D || Wn ? (typeof w == "function" && (Rr(
        e,
        n,
        w,
        a
      ), D = e.memoizedState), (S = Wn || Rm(
        e,
        n,
        S,
        a,
        A,
        D,
        f
      )) ? (N || typeof u.UNSAFE_componentWillMount != "function" && typeof u.componentWillMount != "function" || (typeof u.componentWillMount == "function" && u.componentWillMount(), typeof u.UNSAFE_componentWillMount == "function" && u.UNSAFE_componentWillMount()), typeof u.componentDidMount == "function" && (e.flags |= 4194308)) : (typeof u.componentDidMount == "function" && (e.flags |= 4194308), e.memoizedProps = a, e.memoizedState = D), u.props = a, u.state = D, u.context = f, a = S) : (typeof u.componentDidMount == "function" && (e.flags |= 4194308), a = !1);
    } else {
      u = e.stateNode, or(t, e), f = e.memoizedProps, N = La(n, f), u.props = N, w = e.pendingProps, A = u.context, D = n.contextType, S = hi, typeof D == "object" && D !== null && (S = le(D)), m = n.getDerivedStateFromProps, (D = typeof m == "function" || typeof u.getSnapshotBeforeUpdate == "function") || typeof u.UNSAFE_componentWillReceiveProps != "function" && typeof u.componentWillReceiveProps != "function" || (f !== w || A !== S) && _m(
        e,
        u,
        a,
        S
      ), Wn = !1, A = e.memoizedState, u.state = A, Tl(e, a, u, s), Sl();
      var O = e.memoizedState;
      f !== w || A !== O || Wn || t !== null && t.dependencies !== null && Us(t.dependencies) ? (typeof m == "function" && (Rr(
        e,
        n,
        m,
        a
      ), O = e.memoizedState), (N = Wn || Rm(
        e,
        n,
        N,
        a,
        A,
        O,
        S
      ) || t !== null && t.dependencies !== null && Us(t.dependencies)) ? (D || typeof u.UNSAFE_componentWillUpdate != "function" && typeof u.componentWillUpdate != "function" || (typeof u.componentWillUpdate == "function" && u.componentWillUpdate(a, O, S), typeof u.UNSAFE_componentWillUpdate == "function" && u.UNSAFE_componentWillUpdate(
        a,
        O,
        S
      )), typeof u.componentDidUpdate == "function" && (e.flags |= 4), typeof u.getSnapshotBeforeUpdate == "function" && (e.flags |= 1024)) : (typeof u.componentDidUpdate != "function" || f === t.memoizedProps && A === t.memoizedState || (e.flags |= 4), typeof u.getSnapshotBeforeUpdate != "function" || f === t.memoizedProps && A === t.memoizedState || (e.flags |= 1024), e.memoizedProps = a, e.memoizedState = O), u.props = a, u.state = O, u.context = S, a = N) : (typeof u.componentDidUpdate != "function" || f === t.memoizedProps && A === t.memoizedState || (e.flags |= 4), typeof u.getSnapshotBeforeUpdate != "function" || f === t.memoizedProps && A === t.memoizedState || (e.flags |= 1024), a = !1);
    }
    return u = a, xi(t, e), a = (e.flags & 128) !== 0, u || a ? (u = e.stateNode, n = a && typeof n.getDerivedStateFromError != "function" ? null : u.render(), e.flags |= 1, t !== null && a ? (e.child = Ba(
      e,
      t.child,
      null,
      s
    ), e.child = Ba(
      e,
      null,
      n,
      s
    )) : Pt(t, e, n, s), e.memoizedState = u.state, t = e.child) : t = Un(
      t,
      e,
      s
    ), t;
  }
  function Jm(t, e, n, a) {
    return Na(), e.flags |= 256, Pt(t, e, n, a), e.child;
  }
  var Ur = {
    dehydrated: null,
    treeContext: null,
    retryLane: 0,
    hydrationErrors: null
  };
  function Br(t) {
    return { baseLanes: t, cachePool: Ud() };
  }
  function Hr(t, e, n) {
    return t = t !== null ? t.childLanes & ~n : 0, e && (t |= je), t;
  }
  function km(t, e, n) {
    var a = e.pendingProps, s = !1, u = (e.flags & 128) !== 0, f;
    if ((f = u) || (f = t !== null && t.memoizedState === null ? !1 : (ue.current & 2) !== 0), f && (s = !0, e.flags &= -129), f = (e.flags & 32) !== 0, e.flags &= -33, t === null) {
      if (ft) {
        if (s ? ea(e) : na(), (t = Ut) ? (t = pp(
          t,
          Qe
        ), t = t !== null && t.data !== "&" ? t : null, t !== null && (e.memoizedState = {
          dehydrated: t,
          treeContext: Kn !== null ? { id: cn, overflow: fn } : null,
          retryLane: 536870912,
          hydrationErrors: null
        }, n = Cd(t), n.return = e, e.child = n, te = e, Ut = null)) : t = null, t === null) throw kn(e);
        return Bc(t) ? e.lanes = 32 : e.lanes = 536870912, null;
      }
      return u = a.children, a = a.fallback, s ? (na(), s = e.mode, u = nu(
        { mode: "hidden", children: u },
        s
      ), a = Oa(
        a,
        s,
        n,
        null
      ), u.return = e, a.return = e, u.sibling = a, e.child = u, a = e.child, a.memoizedState = Br(n), a.childLanes = Hr(
        t,
        f,
        n
      ), e.memoizedState = Ur, Dl(null, a)) : (ea(e), Lr(e, u));
    }
    var m = t.memoizedState;
    if (m !== null) {
      var S = m.dehydrated;
      if (S !== null)
        return wb(
          t,
          e,
          u,
          f,
          a,
          S,
          m,
          n
        );
    }
    return s ? (na(), s = a.fallback, u = e.mode, m = t.child, S = m.sibling, a = zn(m, {
      mode: "hidden",
      children: a.children
    }), a.subtreeFlags = m.subtreeFlags & 1206910976, S !== null ? s = zn(S, s) : (s = Oa(
      s,
      u,
      n,
      null
    ), s.flags |= 2), s.return = e, a.return = e, a.sibling = s, e.child = a, Dl(null, a), a = e.child, s = t.child.memoizedState, s === null ? s = Br(n) : (u = s.cachePool, u !== null ? (m = Qt._currentValue, u = u.parent !== m ? { parent: m, pool: m } : u) : u = Ud(), s = {
      baseLanes: s.baseLanes | n,
      cachePool: u
    }), a.memoizedState = s, a.childLanes = Hr(
      t,
      f,
      n
    ), e.memoizedState = Ur, Dl(t.child, a)) : (ea(e), n = t.child, t = n.sibling, n = zn(n, {
      mode: "visible",
      children: a.children
    }), n.return = e, n.sibling = null, t !== null && (f = e.deletions, f === null ? (e.deletions = [t], e.flags |= 16) : f.push(t)), e.child = n, e.memoizedState = null, n);
  }
  function Lr(t, e) {
    return e = nu(
      { mode: "visible", children: e },
      t.mode
    ), e.return = t, t.child = e;
  }
  function nu(t, e) {
    return t = xe(22, t, null, e), t.lanes = 0, t;
  }
  function au(t, e, n) {
    return Ba(e, t.child, null, n), t = Lr(
      e,
      e.pendingProps.children
    ), t.flags |= 2, e.memoizedState = null, t;
  }
  function wb(t, e, n, a, s, u, f, m) {
    if (n)
      return e.flags & 256 ? (ea(e), e.flags &= -257, au(
        t,
        e,
        m
      )) : e.memoizedState !== null ? (na(), e.child = t.child, e.flags |= 128, null) : (na(), u = s.fallback, f = e.mode, s = nu(
        { mode: "visible", children: s.children },
        f
      ), u = Oa(
        u,
        f,
        m,
        null
      ), u.flags |= 2, s.return = e, u.return = e, s.sibling = u, e.child = s, Ba(e, t.child, null, m), s = e.child, s.memoizedState = Br(m), s.childLanes = Hr(
        t,
        a,
        m
      ), e.memoizedState = Ur, Dl(null, s));
    if (ea(e), Bc(u)) {
      if (a = u.nextSibling && u.nextSibling.dataset, a) var S = a.dgst;
      return a = S, a !== "" && (s = Error(o(419)), s.stack = "", s.digest = a, ml({ value: s, source: null, stack: null })), au(
        t,
        e,
        m
      );
    }
    if (Kt || Ra(t, e, m, !1), a = (m & t.childLanes) !== 0, Kt || a) {
      if (ta.current !== null)
        return au(
          t,
          e,
          m
        );
      if (a = _t, a !== null && (s = zh(
        a,
        m
      ), s !== 0 && s !== f.retryLane))
        throw f.retryLane = s, Ca(t, s), De(a, t, s), Vr;
      return Uc(u) || Tu(), au(
        t,
        e,
        m
      );
    }
    return Uc(u) ? (e.flags |= 192, e.child = t.child, null) : (t = f.treeContext, Ut = Ke(u.nextSibling), te = e, ft = !0, Jn = null, Qe = !1, t !== null && zd(e, t), e = Lr(
      e,
      s.children
    ), e.flags |= 134221824, e);
  }
  function Pm(t, e, n) {
    t.lanes |= e;
    var a = t.alternate;
    a !== null && (a.lanes |= e), js(t.return, e, n);
  }
  function Fm(t) {
    for (var e = null; t !== null; ) {
      var n = t.alternate;
      n !== null && Qs(n) === null && (e = t), t = t.sibling;
    }
    return e;
  }
  function iu(t, e, n, a, s, u) {
    var f = t.memoizedState;
    f === null ? t.memoizedState = {
      isBackwards: e,
      rendering: null,
      renderingStartTime: 0,
      last: a,
      tail: n,
      tailMode: s,
      treeForkCount: u
    } : (f.isBackwards = e, f.rendering = null, f.renderingStartTime = 0, f.last = a, f.tail = n, f.tailMode = s, f.treeForkCount = u);
  }
  function Yr(t) {
    var e = t.child;
    for (t.child = null; e !== null; ) {
      var n = e.sibling;
      e.sibling = t.child, t.child = e, e = n;
    }
  }
  function qr(t, e, n) {
    var a = e.pendingProps, s = a.revealOrder, u = a.tail;
    a = a.children;
    var f = ue.current;
    if (e.flags & 128)
      return xl(e, f), null;
    var m = (f & 2) !== 0;
    if (m ? (f = f & 1 | 2, e.flags |= 128) : f &= 1, xl(e, f), s === "backwards" && t !== null ? (Yr(t), Pt(t, e, a, n), Yr(t)) : Pt(t, e, a, n), a = ft ? dl : 0, !m && t !== null && (t.flags & 128) !== 0)
      t: for (t = e.child; t !== null; ) {
        if (t.tag === 13)
          t.memoizedState !== null && Pm(t, n, e);
        else if (t.tag === 19)
          Pm(t, n, e);
        else if (t.child !== null) {
          t.child.return = t, t = t.child;
          continue;
        }
        if (t === e) break t;
        for (; t.sibling === null; ) {
          if (t.return === null || t.return === e)
            break t;
          t = t.return;
        }
        t.sibling.return = t.return, t = t.sibling;
      }
    switch (s) {
      case "backwards":
        n = Fm(e.child), n === null ? (s = e.child, e.child = null) : (s = n.sibling, n.sibling = null, Yr(e)), iu(
          e,
          !0,
          s,
          null,
          u,
          a
        );
        break;
      case "unstable_legacy-backwards":
        for (n = null, s = e.child, e.child = null; s !== null; ) {
          if (t = s.alternate, t !== null && Qs(t) === null) {
            e.child = s;
            break;
          }
          t = s.sibling, s.sibling = n, n = s, s = t;
        }
        iu(
          e,
          !0,
          n,
          null,
          u,
          a
        );
        break;
      case "together":
        iu(
          e,
          !1,
          null,
          null,
          void 0,
          a
        );
        break;
      case "independent":
        e.memoizedState = null;
        break;
      default:
        n = Fm(e.child), n === null ? (s = e.child, e.child = null) : (s = n.sibling, n.sibling = null), iu(
          e,
          !1,
          s,
          n,
          u,
          a
        );
    }
    return e.child;
  }
  function Wm(t, e, n) {
    var a = e.pendingProps;
    return Pn(e, e.type, a.value), Pt(t, e, a.children, n), e.child;
  }
  function Un(t, e, n) {
    if (t !== null && (e.dependencies = t.dependencies), sa |= e.lanes, (n & e.childLanes) === 0)
      if (t !== null) {
        if (Ra(
          t,
          e,
          n,
          !1
        ), (n & e.childLanes) === 0)
          return null;
      } else return null;
    if (t !== null && e.child !== t.child)
      throw Error(o(153));
    if (e.child !== null) {
      for (t = e.child, n = zn(t, t.pendingProps), e.child = n, n.return = e; t.sibling !== null; )
        t = t.sibling, n = n.sibling = zn(t, t.pendingProps), n.return = e;
      n.sibling = null;
    }
    return e.child;
  }
  function Gr(t, e) {
    return (t.lanes & e) !== 0 ? !0 : (t = t.dependencies, !!(t !== null && Us(t)));
  }
  function Vb(t, e, n) {
    switch (e.tag) {
      case 3:
        rs(e, e.stateNode.containerInfo), Pn(e, Qt, t.memoizedState.cache), Na();
        break;
      case 27:
      case 5:
        yo(e);
        break;
      case 4:
        rs(e, e.stateNode.containerInfo);
        break;
      case 10:
        Pn(
          e,
          e.type,
          e.memoizedProps.value
        );
        break;
      case 31:
        if (e.memoizedState !== null)
          return e.flags |= 128, dr(e), null;
        break;
      case 13:
        var a = e.memoizedState;
        if (a !== null) {
          if (a.dehydrated !== null)
            return ea(e), e.flags |= 128, null;
          a = Ra(
            t,
            e,
            n,
            !1
          );
          var s = e.child.childLanes;
          return a || (n & s) !== 0 ? km(t, e, n) : (ea(e), t = Un(
            t,
            e,
            n
          ), t !== null ? t.sibling : null);
        }
        ea(e);
        break;
      case 19:
        if (e.flags & 128)
          return qr(
            t,
            e,
            n
          );
        if (s = (t.flags & 128) !== 0, a = (n & e.childLanes) !== 0, a || (Ra(
          t,
          e,
          n,
          !1
        ), a = (n & e.childLanes) !== 0), s) {
          if (a)
            return qr(
              t,
              e,
              n
            );
          e.flags |= 128;
        }
        if (s = e.memoizedState, s !== null && (s.rendering = null, s.tail = null, s.lastEffect = null), xl(e, ue.current), a) break;
        return null;
      case 22:
        return e.lanes = 0, Gm(
          t,
          e,
          n,
          e.pendingProps
        );
      case 24:
        Pn(e, Qt, t.memoizedState.cache);
    }
    return Un(t, e, n);
  }
  function Im(t, e, n) {
    if (t !== null)
      if (t.memoizedProps !== e.pendingProps)
        Kt = !0;
      else {
        if (!Gr(t, n) && (e.flags & 128) === 0)
          return Kt = !1, Vb(
            t,
            e,
            n
          );
        Kt = (t.flags & 131072) !== 0;
      }
    else
      Kt = !1, ft && (e.flags & 1048576) !== 0 && Nd(e, dl, e.index);
    switch (e.lanes = 0, e.tag) {
      case 16:
        t: {
          var a = e.pendingProps;
          if (t = ja(e.elementType), e.type = t, typeof t == "function")
            Po(t) ? (a = La(t, a), e.tag = 1, e = Km(
              null,
              e,
              t,
              a,
              n
            )) : (e.tag = 0, e = jr(
              null,
              e,
              t,
              a,
              n
            ));
          else {
            if (t != null) {
              var s = t.$$typeof;
              if (s === q) {
                e.tag = 11, e = Lm(
                  null,
                  e,
                  t,
                  a,
                  n
                );
                break t;
              } else if (s === ct) {
                e.tag = 14, e = Ym(
                  null,
                  e,
                  t,
                  a,
                  n
                );
                break t;
              } else if (s === zt) {
                e.tag = 10, e.type = t, e = Wm(
                  null,
                  e,
                  n
                );
                break t;
              }
            }
            throw e = St(t) || t, Error(o(306, e, ""));
          }
        }
        return e;
      case 0:
        return jr(
          t,
          e,
          e.type,
          e.pendingProps,
          n
        );
      case 1:
        return a = e.type, s = La(
          a,
          e.pendingProps
        ), Km(
          t,
          e,
          a,
          s,
          n
        );
      case 3:
        t: {
          if (rs(
            e,
            e.stateNode.containerInfo
          ), t === null) throw Error(o(387));
          a = e.pendingProps;
          var u = e.memoizedState;
          s = u.element, or(t, e), Tl(e, a, null, n);
          var f = e.memoizedState;
          if (a = f.cache, Pn(e, Qt, a), a !== u.cache && nr(
            e,
            [Qt],
            n,
            !0
          ), Sl(), a = f.element, u.isDehydrated)
            if (u = {
              element: a,
              isDehydrated: !1,
              cache: f.cache
            }, e.updateQueue.baseState = u, e.memoizedState = u, e.flags & 256) {
              e = Jm(
                t,
                e,
                a,
                n
              );
              break t;
            } else if (a !== s) {
              s = qe(
                Error(o(424)),
                e
              ), ml(s), e = Jm(
                t,
                e,
                a,
                n
              );
              break t;
            } else
              for (t = e.stateNode.containerInfo, t.nodeType === 9 ? t = t.body : t = t.nodeName === "HTML" ? t.ownerDocument.body : t, Ut = Ke(t.firstChild), te = e, ft = !0, Jn = null, Qe = !0, n = Gd(
                e,
                null,
                a,
                n
              ), e.child = n; n; )
                n.flags = n.flags & -3 | 134221824, n = n.sibling;
          else {
            if (Na(), a === s) {
              e = Un(
                t,
                e,
                n
              );
              break t;
            }
            Pt(t, e, a, n);
          }
          e = e.child;
        }
        return e;
      case 26:
        return xi(t, e), t === null ? (n = Ep(
          e.type,
          null,
          e.pendingProps,
          null
        )) ? e.memoizedState = n : ft || (e.stateNode = np(
          e.type,
          e.pendingProps,
          qn.current,
          e
        )) : e.memoizedState = Ep(
          e.type,
          t.memoizedProps,
          e.pendingProps,
          t.memoizedState
        ), null;
      case 27:
        return yo(e), t === null && ft && (a = e.stateNode = bp(
          e.type,
          e.pendingProps,
          qn.current
        ), te = e, Qe = !0, s = Ut, ca(e.type) ? (Hc = s, Ut = Ke(a.firstChild)) : Ut = s), Pt(
          t,
          e,
          e.pendingProps.children,
          n
        ), xi(t, e), t === null && (e.flags |= 4194304), e.child;
      case 5:
        return t === null && ft && ((s = a = Ut) && (a = OS(
          a,
          e.type,
          e.pendingProps,
          Qe
        ), a !== null ? (e.stateNode = a, te = e, Ut = Ke(a.firstChild), Qe = !1, s = !0) : s = !1), s || kn(e)), yo(e), s = e.type, u = e.pendingProps, f = t !== null ? t.memoizedProps : null, a = u.children, Nc(s, u) ? a = null : f !== null && Nc(s, f) && (e.flags |= 32), e.memoizedState !== null && (s = pr(
          t,
          e,
          Eb,
          null,
          null,
          n
        ), Yi._currentValue = s), xi(t, e), Pt(t, e, a, n), e.child;
      case 6:
        return t === null && ft && ((t = n = Ut) && (n = NS(
          n,
          e.pendingProps,
          Qe
        ), n !== null ? (e.stateNode = n, te = e, Ut = null, t = !0) : t = !1), t || kn(e)), null;
      case 13:
        return km(t, e, n);
      case 4:
        return rs(
          e,
          e.stateNode.containerInfo
        ), a = e.pendingProps, t === null ? e.child = Ba(
          e,
          null,
          a,
          n
        ) : Pt(t, e, a, n), e.child;
      case 11:
        return Lm(
          t,
          e,
          e.type,
          e.pendingProps,
          n
        );
      case 7:
        return a = e.pendingProps, xi(t, e), Pt(t, e, a, n), e.child;
      case 8:
        return Pt(
          t,
          e,
          e.pendingProps.children,
          n
        ), e.child;
      case 12:
        return Pt(
          t,
          e,
          e.pendingProps.children,
          n
        ), e.child;
      case 10:
        return Wm(t, e, n);
      case 9:
        return s = e.type._context, a = e.pendingProps.children, _a(e), s = le(s), a = a(s), e.flags |= 1, Pt(t, e, a, n), e.child;
      case 14:
        return Ym(
          t,
          e,
          e.type,
          e.pendingProps,
          n
        );
      case 15:
        return qm(
          t,
          e,
          e.type,
          e.pendingProps,
          n
        );
      case 19:
        return qr(t, e, n);
      case 31:
        return _b(t, e, n);
      case 22:
        return Gm(
          t,
          e,
          n,
          e.pendingProps
        );
      case 24:
        return _a(e), a = le(Qt), t === null ? (s = lr(), s === null && (s = _t, u = ar(), s.pooledCache = u, u.refCount++, u !== null && (s.pooledCacheLanes |= n), s = u), e.memoizedState = { parent: a, cache: s }, ur(e), Pn(e, Qt, s)) : ((t.lanes & n) !== 0 && (or(t, e), Tl(e, null, null, n), Sl()), s = t.memoizedState, u = e.memoizedState, s.parent !== a ? (s = { parent: a, cache: a }, e.memoizedState = s, e.lanes === 0 && (e.memoizedState = e.updateQueue.baseState = s), Pn(e, Qt, a)) : (a = u.cache, Pn(e, Qt, a), a !== s.cache && nr(
          e,
          [Qt],
          n,
          !0
        ))), Pt(
          t,
          e,
          e.pendingProps.children,
          n
        ), e.child;
      case 30:
        return e.stateNode === null && (e.stateNode = {
          autoName: null,
          paired: null,
          clones: null,
          ref: null
        }), a = e.pendingProps, a.name != null && a.name !== "auto" ? e.flags |= t === null ? 18882560 : 18874368 : ft && ws(e), t !== null && t.memoizedProps.name !== a.name ? e.flags |= 4194816 : xi(t, e), Pt(t, e, a.children, n), e.child;
      case 29:
        throw e.pendingProps;
    }
    throw Error(o(156, e.tag));
  }
  function Bn(t) {
    t.flags |= 4;
  }
  function Xr(t, e, n, a, s) {
    var u;
    if ((u = (t.mode & 32) !== 0) && (u = n === null ? Cp(e, a) : Cp(e, a) && (a.src !== n.src || a.srcSet !== n.srcSet)), u) {
      if (t.flags |= 16777216, (s & 335544128) === s)
        if (t.stateNode.complete) t.flags |= 8192;
        else if (wy()) t.flags |= 8192;
        else
          throw Ua = Ys, sr;
    } else t.flags &= -16777217;
  }
  function $m(t, e) {
    if (e.type !== "stylesheet" || (e.state.loading & 4) !== 0)
      t.flags &= -16777217;
    else if (t.flags |= 16777216, !Op(e))
      if (wy()) t.flags |= 8192;
      else
        throw Ua = Ys, sr;
  }
  function lu(t, e) {
    e !== null && (t.flags |= 4), t.flags & 16384 && (e = t.tag !== 22 ? Ch() : 536870912, t.lanes |= e, Ci |= e);
  }
  function Cl(t, e) {
    if (!ft)
      switch (t.tailMode) {
        case "visible":
          break;
        case "collapsed":
          for (var n = t.tail, a = null; n !== null; )
            n.alternate !== null && (a = n), n = n.sibling;
          a === null ? e || t.tail === null ? t.tail = null : t.tail.sibling = null : a.sibling = null;
          break;
        default:
          for (e = t.tail, n = null; e !== null; )
            e.alternate !== null && (n = e), e = e.sibling;
          n === null ? t.tail = null : n.sibling = null;
      }
  }
  function Bt(t) {
    var e = t.alternate !== null && t.alternate.child === t.child, n = 0, a = 0;
    if (e)
      for (var s = t.child; s !== null; )
        n |= s.lanes | s.childLanes, a |= s.subtreeFlags & 1206910976, a |= s.flags & 1206910976, s.return = t, s = s.sibling;
    else
      for (s = t.child; s !== null; )
        n |= s.lanes | s.childLanes, a |= s.subtreeFlags, a |= s.flags, s.return = t, s = s.sibling;
    return t.subtreeFlags |= a, t.childLanes = n, e;
  }
  function jb(t, e, n) {
    var a = e.pendingProps;
    switch (Io(e), e.tag) {
      case 16:
      case 15:
      case 0:
      case 11:
      case 7:
      case 8:
      case 12:
      case 9:
      case 14:
        return Bt(e), null;
      case 1:
        return Bt(e), null;
      case 3:
        return n = e.stateNode, a = null, t !== null && (a = t.memoizedState.cache), e.memoizedState.cache !== a && (e.flags |= 2048), wn(Qt), $a(), n.pendingContext && (n.context = n.pendingContext, n.pendingContext = null), (t === null || t.child === null) && (yi(e) ? Bn(e) : t === null || t.memoizedState.isDehydrated && (e.flags & 256) === 0 || (e.flags |= 1024, tr())), Bt(e), null;
      case 26:
        var s = e.type, u = e.memoizedState;
        return t === null ? (Bn(e), u !== null ? (Bt(e), $m(e, u)) : (Bt(e), Xr(
          e,
          s,
          null,
          a,
          n
        ))) : u ? u !== t.memoizedState ? (Bn(e), Bt(e), $m(e, u)) : (Bt(e), e.flags &= -16777217) : (t = t.memoizedProps, t !== a && Bn(e), Bt(e), Xr(
          e,
          s,
          t,
          a,
          n
        )), null;
      case 27:
        if (cs(e), n = qn.current, s = e.type, t !== null && e.stateNode != null)
          t.memoizedProps !== a && Bn(e);
        else {
          if (!a) {
            if (e.stateNode === null)
              throw Error(o(166));
            return Bt(e), e.subtreeFlags &= -33554433, null;
          }
          t = on.current, yi(e) ? Rd(e) : (t = bp(s, a, n), e.stateNode = t, Bn(e));
        }
        return Bt(e), e.subtreeFlags &= -33554433, null;
      case 5:
        if (cs(e), s = e.type, t !== null && e.stateNode != null)
          t.memoizedProps !== a && Bn(e);
        else {
          if (!a) {
            if (e.stateNode === null)
              throw Error(o(166));
            return Bt(e), e.subtreeFlags &= -33554433, null;
          }
          if (u = on.current, yi(e))
            Rd(e);
          else {
            var f = Hl(
              qn.current
            );
            switch (u) {
              case 1:
                u = f.createElementNS(
                  "http://www.w3.org/2000/svg",
                  s
                );
                break;
              case 2:
                u = f.createElementNS(
                  "http://www.w3.org/1998/Math/MathML",
                  s
                );
                break;
              default:
                switch (s) {
                  case "svg":
                    u = f.createElementNS(
                      "http://www.w3.org/2000/svg",
                      s
                    );
                    break;
                  case "math":
                    u = f.createElementNS(
                      "http://www.w3.org/1998/Math/MathML",
                      s
                    );
                    break;
                  case "script":
                    u = f.createElement("div"), u.innerHTML = "<script><\/script>", u = u.removeChild(
                      u.firstChild
                    );
                    break;
                  case "select":
                    u = typeof a.is == "string" ? f.createElement("select", {
                      is: a.is
                    }) : f.createElement("select"), a.multiple ? u.multiple = !0 : a.size && (u.size = a.size);
                    break;
                  default:
                    u = typeof a.is == "string" ? f.createElement(s, { is: a.is }) : f.createElement(s);
                }
            }
            u[ie] = e, u[Te] = a;
            t: for (f = e.child; f !== null; ) {
              if (f.tag === 5 || f.tag === 6)
                u.appendChild(f.stateNode);
              else if (f.tag !== 4 && f.tag !== 27 && f.child !== null) {
                f.child.return = f, f = f.child;
                continue;
              }
              if (f === e) break t;
              for (; f.sibling === null; ) {
                if (f.return === null || f.return === e)
                  break t;
                f = f.return;
              }
              f.sibling.return = f.return, f = f.sibling;
            }
            e.stateNode = u;
            t: switch (re(u, s, a), s) {
              case "button":
              case "input":
              case "select":
              case "textarea":
                a = !!a.autoFocus;
                break t;
              case "img":
                a = !0;
                break t;
              default:
                a = !1;
            }
            a && Bn(e);
          }
        }
        return Bt(e), e.subtreeFlags &= -33554433, Xr(
          e,
          e.type,
          t === null ? null : t.memoizedProps,
          e.pendingProps,
          n
        ), null;
      case 6:
        if (t && e.stateNode != null)
          t.memoizedProps !== a && Bn(e);
        else {
          if (typeof a != "string" && e.stateNode === null)
            throw Error(o(166));
          if (t = qn.current, yi(e)) {
            if (t = e.stateNode, n = e.memoizedProps, a = null, s = te, s !== null)
              switch (s.tag) {
                case 27:
                case 5:
                  a = s.memoizedProps;
              }
            t[ie] = e, t = !!(t.nodeValue === n || a !== null && a.suppressHydrationWarning === !0 || Iy(t.nodeValue, n)), t || kn(e, !0);
          } else
            t = Hl(t).createTextNode(
              a
            ), t[ie] = e, e.stateNode = t;
        }
        return Bt(e), null;
      case 31:
        if (n = e.memoizedState, t === null || t.memoizedState !== null) {
          if (a = yi(e), n !== null) {
            if (t === null) {
              if (!a) throw Error(o(318));
              if (t = e.memoizedState, t = t !== null ? t.dehydrated : null, !t) throw Error(o(557));
              t[ie] = e;
            } else
              Na(), (e.flags & 128) === 0 && (e.memoizedState = null), e.flags |= 4;
            Bt(e), t = !1;
          } else
            n = tr(), t !== null && t.memoizedState !== null && (t.memoizedState.hydrationErrors = n), t = !0;
          if (!t)
            return e.flags & 256 ? (_e(e), e) : (_e(e), null);
          if ((e.flags & 128) !== 0)
            throw Error(o(558));
        }
        return Bt(e), null;
      case 13:
        if (a = e.memoizedState, t === null || t.memoizedState !== null && t.memoizedState.dehydrated !== null) {
          if (s = yi(e), a !== null && a.dehydrated !== null) {
            if (t === null) {
              if (!s) throw Error(o(318));
              if (s = e.memoizedState, s = s !== null ? s.dehydrated : null, !s) throw Error(o(317));
              s[ie] = e;
            } else
              Na(), (e.flags & 128) === 0 && (e.memoizedState = null), e.flags |= 4;
            Bt(e), s = !1;
          } else
            s = tr(), t !== null && t.memoizedState !== null && (t.memoizedState.hydrationErrors = s), s = !0;
          if (!s)
            return e.flags & 256 ? (_e(e), e) : (_e(e), null);
        }
        return _e(e), (e.flags & 128) !== 0 ? (e.lanes = n, e) : (n = a !== null, t = t !== null && t.memoizedState !== null, n && (a = e.child, s = null, a.alternate !== null && a.alternate.memoizedState !== null && a.alternate.memoizedState.cachePool !== null && (s = a.alternate.memoizedState.cachePool.pool), u = null, a.memoizedState !== null && a.memoizedState.cachePool !== null && (u = a.memoizedState.cachePool.pool), u !== s && (a.flags |= 2048)), n !== t && n && (e.child.flags |= 8192), lu(e, e.updateQueue), Bt(e), null);
      case 4:
        return $a(), t === null && Ac(e.stateNode.containerInfo), e.flags |= 67108864, Bt(e), null;
      case 10:
        return wn(e.type), Bt(e), null;
      case 19:
        if (mr(e), a = e.memoizedState, a === null) return Bt(e), null;
        if (s = (e.flags & 128) !== 0, u = a.rendering, u === null)
          if (s) Cl(a, !1);
          else {
            if (qt !== 0 || t !== null && (t.flags & 128) !== 0)
              for (t = e.child; t !== null; ) {
                if (u = Qs(t), u !== null) {
                  for (e.flags |= 128, Cl(a, !1), t = u.updateQueue, e.updateQueue = t, lu(e, t), e.subtreeFlags = 0, t = n, n = e.child; n !== null; )
                    Dd(n, t), n = n.sibling;
                  return xl(
                    e,
                    ue.current & 1 | 2
                  ), ft && Rn(e, a.treeForkCount), e.child;
                }
                t = t.sibling;
              }
            a.tail !== null && Ce() > gu && (e.flags |= 128, s = !0, Cl(a, !1), e.lanes = 4194304);
          }
        else {
          if (!s)
            if (t = Qs(u), t !== null) {
              if (e.flags |= 128, s = !0, t = t.updateQueue, e.updateQueue = t, lu(e, t), Cl(a, !0), a.tail === null && a.tailMode !== "collapsed" && a.tailMode !== "visible" && !u.alternate && !ft)
                return Bt(e), null;
            } else
              2 * Ce() - a.renderingStartTime > gu && n !== 536870912 && (e.flags |= 128, s = !0, Cl(a, !1), e.lanes = 4194304);
          a.isBackwards ? (u.sibling = e.child, e.child = u) : (t = a.last, t !== null ? t.sibling = u : e.child = u, a.last = u);
        }
        if (a.tail !== null) {
          t = a.tail;
          t: {
            for (n = t; n !== null; ) {
              if (n.alternate !== null) {
                n = !1;
                break t;
              }
              n = n.sibling;
            }
            n = !0;
          }
          return a.rendering = t, a.tail = t.sibling, a.renderingStartTime = Ce(), t.sibling = null, u = ue.current, u = s ? u & 1 | 2 : u & 1, a.tailMode === "visible" || a.tailMode === "collapsed" || !n || ft ? xl(e, u) : (n = u, jt(se, e), jt(ue, n), me === null && (me = e)), ft && Rn(e, a.treeForkCount), t;
        }
        return Bt(e), null;
      case 22:
      case 23:
        return _e(e), hr(), a = e.memoizedState !== null, t !== null ? t.memoizedState !== null !== a && (e.flags |= 8192) : a && (e.flags |= 8192), a ? (n & 536870912) !== 0 && (e.flags & 128) === 0 && (Bt(e), e.subtreeFlags & 6 && (e.flags |= 8192)) : Bt(e), n = e.updateQueue, n !== null && lu(e, n.retryQueue), n = null, t !== null && t.memoizedState !== null && t.memoizedState.cachePool !== null && (n = t.memoizedState.cachePool.pool), a = null, e.memoizedState !== null && e.memoizedState.cachePool !== null && (a = e.memoizedState.cachePool.pool), a !== n && (e.flags |= 2048), t !== null && ae(Va), null;
      case 24:
        return n = null, t !== null && (n = t.memoizedState.cache), e.memoizedState.cache !== n && (e.flags |= 2048), wn(Qt), Bt(e), null;
      case 25:
        return null;
      case 30:
        return e.flags |= 33554432, Bt(e), null;
    }
    throw Error(o(156, e.tag));
  }
  function Ub(t, e) {
    switch (Io(e), e.tag) {
      case 1:
        return t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 3:
        return wn(Qt), $a(), t = e.flags, (t & 65536) !== 0 && (t & 128) === 0 ? (e.flags = t & -65537 | 128, e) : null;
      case 26:
      case 27:
      case 5:
        return cs(e), null;
      case 31:
        if (e.memoizedState !== null) {
          if (_e(e), e.alternate === null)
            throw Error(o(340));
          Na();
        }
        return t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 13:
        if (_e(e), t = e.memoizedState, t !== null && t.dehydrated !== null) {
          if (e.alternate === null)
            throw Error(o(340));
          Na();
        }
        return t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 19:
        return mr(e), t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, t = e.memoizedState, t !== null && (t.rendering = null, t.tail = null), e.flags |= 4, e) : null;
      case 4:
        return $a(), null;
      case 10:
        return wn(e.type), null;
      case 22:
      case 23:
        return _e(e), hr(), t !== null && ae(Va), t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 24:
        return wn(Qt), null;
      case 25:
        return null;
      default:
        return null;
    }
  }
  function ty(t, e) {
    switch (Io(e), e.tag) {
      case 3:
        wn(Qt), $a();
        break;
      case 26:
      case 27:
      case 5:
        cs(e);
        break;
      case 4:
        $a();
        break;
      case 31:
        e.memoizedState !== null && _e(e);
        break;
      case 13:
        _e(e);
        break;
      case 19:
        mr(e);
        break;
      case 10:
        wn(e.type);
        break;
      case 22:
      case 23:
        _e(e), hr(), t !== null && ae(Va);
        break;
      case 24:
        wn(Qt);
    }
  }
  function Ol(t, e) {
    try {
      var n = e.updateQueue, a = n !== null ? n.lastEffect : null;
      if (a !== null) {
        var s = a.next;
        n = s;
        do {
          if ((n.tag & t) === t) {
            a = void 0;
            var u = n.create, f = n.inst;
            a = u(), f.destroy = a;
          }
          n = n.next;
        } while (n !== s);
      }
    } catch (m) {
      Dt(e, e.return, m);
    }
  }
  function aa(t, e, n) {
    try {
      var a = e.updateQueue, s = a !== null ? a.lastEffect : null;
      if (s !== null) {
        var u = s.next;
        a = u;
        do {
          if ((a.tag & t) === t) {
            var f = a.inst, m = f.destroy;
            if (m !== void 0) {
              f.destroy = void 0, s = e;
              var S = n, D = m;
              try {
                D();
              } catch (N) {
                Dt(
                  s,
                  S,
                  N
                );
              }
            }
          }
          a = a.next;
        } while (a !== u);
      }
    } catch (N) {
      Dt(e, e.return, N);
    }
  }
  function ey(t) {
    var e = t.updateQueue;
    if (e !== null) {
      var n = t.stateNode;
      try {
        Qd(e, n);
      } catch (a) {
        Dt(t, t.return, a);
      }
    }
  }
  function ny(t, e, n) {
    n.props = La(
      t.type,
      t.memoizedProps
    ), n.state = t.memoizedState;
    try {
      n.componentWillUnmount();
    } catch (a) {
      Dt(t, e, a);
    }
  }
  function hn(t, e) {
    try {
      var n = t.ref;
      if (n !== null) {
        switch (t.tag) {
          case 26:
          case 27:
          case 5:
            var a = t.stateNode;
            break;
          case 30:
            var s = t.stateNode, u = On(t.memoizedProps, s);
            (s.ref === null || s.ref.name !== u) && (s.ref = rp(u)), a = s.ref;
            break;
          case 7:
            if (t.stateNode === null) {
              var f = new Be(t);
              p(
                t.child,
                !1,
                DS,
                f,
                void 0,
                void 0
              ), t.stateNode = f;
            }
            a = t.stateNode;
            break;
          default:
            a = t.stateNode;
        }
        typeof n == "function" ? t.refCleanup = n(a) : n.current = a;
      }
    } catch (m) {
      Dt(t, e, m);
    }
  }
  function oe(t, e) {
    var n = t.ref, a = t.refCleanup;
    if (n !== null)
      if (typeof a == "function")
        try {
          a();
        } catch (s) {
          Dt(t, e, s);
        } finally {
          t.refCleanup = null, t = t.alternate, t != null && (t.refCleanup = null);
        }
      else if (typeof n == "function")
        try {
          n(null);
        } catch (s) {
          Dt(t, e, s);
        }
      else n.current = null;
  }
  function su(t, e) {
    if ((t.tag === 5 || t.tag === 27 || t.tag === 6) && t.alternate === null && e !== null)
      for (var n = 0; n < e.length; n++)
        yp(
          t.stateNode,
          e[n]
        );
  }
  function ay(t) {
    for (var e = t.return; e !== null && (Zr(e) && yp(t.stateNode, e.stateNode), !Qr(e)); )
      e = e.return;
  }
  function Nl(t) {
    for (var e = t.return; e !== null && (Zr(e) && CS(t.stateNode, e.stateNode), !Qr(e)); )
      e = e.return;
  }
  function Qr(t) {
    return t.tag === 5 || t.tag === 3 || t.tag === 27;
  }
  function Zr(t) {
    return t && t.tag === 7 && t.stateNode !== null;
  }
  function Kr(t) {
    var e = t.type, n = t.memoizedProps, a = t.stateNode;
    try {
      t: switch (e) {
        case "button":
        case "input":
        case "select":
        case "textarea":
          n.autoFocus && a.focus();
          break t;
        case "img":
          n.src ? a.src = n.src : n.srcSet && (a.srcset = n.srcSet);
      }
    } catch (s) {
      Dt(t, t.return, s);
    }
  }
  function Jr(t, e, n) {
    try {
      var a = t.stateNode;
      oS(a, t.type, n, e), a[Te] = e;
    } catch (s) {
      Dt(t, t.return, s);
    }
  }
  function iy(t) {
    return t.tag === 5 || t.tag === 3 || t.tag === 26 || t.tag === 27 && ca(t.type) || t.tag === 4;
  }
  function kr(t) {
    t: for (; ; ) {
      for (; t.sibling === null; ) {
        if (t.return === null || iy(t.return)) return null;
        t = t.return;
      }
      for (t.sibling.return = t.return, t = t.sibling; t.tag !== 5 && t.tag !== 6 && t.tag !== 18; ) {
        if (t.tag === 27 && ca(t.type) || t.flags & 2 || t.child === null || t.tag === 4) continue t;
        t.child.return = t, t = t.child;
      }
      if (!(t.flags & 2)) return t.stateNode;
    }
  }
  function Pr(t, e, n, a) {
    var s = t.tag;
    if (s === 5 || s === 6)
      s = t.stateNode, e ? (n.nodeType === 9 ? n.body : n.nodeName === "HTML" ? n.ownerDocument.body : n).insertBefore(s, e) : (e = n.nodeType === 9 ? n.body : n.nodeName === "HTML" ? n.ownerDocument.body : n, e.appendChild(s), n = n._reactRootContainer, n != null || e.onclick !== null || (e.onclick = rn)), su(t, a), Tt = !0;
    else if (s !== 4 && (s === 27 && (su(t, a), a = null, ca(t.type) && (n = t.stateNode, e = null)), t = t.child, t !== null))
      for (Pr(
        t,
        e,
        n,
        a
      ), t = t.sibling; t !== null; )
        Pr(
          t,
          e,
          n,
          a
        ), t = t.sibling;
  }
  function uu(t, e, n, a) {
    var s = t.tag;
    if (s === 5 || s === 6)
      s = t.stateNode, e ? n.insertBefore(s, e) : n.appendChild(s), su(t, a), Tt = !0;
    else if (s !== 4 && (s === 27 && (su(t, a), a = null, ca(t.type) && (n = t.stateNode)), t = t.child, t !== null))
      for (uu(
        t,
        e,
        n,
        a
      ), t = t.sibling; t !== null; )
        uu(
          t,
          e,
          n,
          a
        ), t = t.sibling;
  }
  function ly(t) {
    var e = t.stateNode, n = t.memoizedProps;
    try {
      for (var a = t.type, s = e.attributes; s.length; )
        e.removeAttributeNode(s[0]);
      re(e, a, n), e[ie] = t, e[Te] = n;
    } catch (u) {
      Dt(t, t.return, u);
    }
  }
  var ou = !1, we = null;
  function sy(t) {
    (t.tag === 30 || (t.subtreeFlags & 33554432) !== 0) && (ou = !0);
  }
  var dn = null;
  function uy() {
    var t = dn;
    return dn = null, t;
  }
  var Ee = 0;
  function Ei(t, e, n, a, s) {
    return Ee = 0, oy(
      t.child,
      e,
      n,
      a,
      s
    );
  }
  function oy(t, e, n, a, s) {
    for (var u = !1; t !== null; ) {
      if (t.tag === 5) {
        var f = t.stateNode;
        if (a !== null) {
          var m = _c(f);
          a.push(m), m.view && (u = !0);
        } else
          u || _c(f).view && (u = !0);
        ou = !0, up(
          f,
          Ee === 0 ? e : e + "_" + Ee,
          n
        ), Ee++;
      } else (t.tag !== 22 || t.memoizedState === null) && (t.tag === 30 && s || oy(
        t.child,
        e,
        n,
        a,
        s
      ) && (u = !0));
      t = t.sibling;
    }
    return u;
  }
  function mn(t, e) {
    for (; t !== null; )
      t.tag === 5 ? op(t.stateNode, t.memoizedProps) : (t.tag !== 22 || t.memoizedState === null) && (t.tag === 30 && e || mn(
        t.child,
        e
      )), t = t.sibling;
  }
  function ru(t) {
    if ((t.subtreeFlags & 18874368) !== 0)
      for (t = t.child; t !== null; ) {
        if ((t.tag !== 22 || t.memoizedState === null) && (ru(t), t.tag === 30 && (t.flags & 18874368) !== 0 && t.stateNode.paired)) {
          var e = t.memoizedProps;
          if (e.name == null || e.name === "auto")
            throw Error(o(544));
          var n = e.name;
          e = Nn(e.default, e.share), e !== "none" && (Ei(
            t,
            n,
            e,
            null,
            !1
          ) || mn(t.child, !1));
        }
        t = t.sibling;
      }
  }
  function Fr(t, e) {
    if (t.tag === 30) {
      var n = t.stateNode, a = t.memoizedProps, s = On(a, n), u = Nn(
        a.default,
        n.paired ? a.share : a.enter
      );
      u !== "none" ? Ei(t, s, u, null, !1) ? (ru(t), n.paired || e || Ri(t, a.onEnter)) : mn(t.child, !1) : ru(t);
    } else if ((t.subtreeFlags & 33554432) !== 0)
      for (t = t.child; t !== null; )
        Fr(t, e), t = t.sibling;
    else ru(t);
  }
  function Wr(t) {
    if (we !== null && we.size !== 0) {
      var e = we;
      if ((t.subtreeFlags & 18874368) !== 0)
        for (t = t.child; t !== null; ) {
          if (t.tag !== 22 || t.memoizedState === null) {
            if (t.tag === 30 && (t.flags & 18874368) !== 0) {
              var n = t.memoizedProps, a = n.name;
              if (a != null && a !== "auto") {
                var s = e.get(a);
                if (s !== void 0) {
                  var u = Nn(
                    n.default,
                    n.share
                  );
                  if (u !== "none" && (Ei(
                    t,
                    a,
                    u,
                    null,
                    !1
                  ) ? (u = t.stateNode, s.paired = u, u.paired = s, Ri(t, n.onShare)) : mn(t.child, !1)), e.delete(a), e.size === 0) break;
                }
              }
            }
            Wr(t);
          }
          t = t.sibling;
        }
    }
  }
  function Ir(t) {
    if (t.tag === 30) {
      var e = t.memoizedProps, n = On(e, t.stateNode), a = we !== null ? we.get(n) : void 0, s = Nn(
        e.default,
        a !== void 0 ? e.share : e.exit
      );
      s !== "none" && (Ei(t, n, s, null, !1) ? a !== void 0 ? (s = t.stateNode, a.paired = s, s.paired = a, we.delete(n), Ri(t, e.onShare)) : Ri(t, e.onExit) : mn(t.child, !1)), we !== null && Wr(t);
    } else if ((t.subtreeFlags & 33554432) !== 0)
      for (t = t.child; t !== null; )
        Ir(t), t = t.sibling;
    else
      we !== null && Wr(t);
  }
  function ry(t) {
    for (t = t.child; t !== null; ) {
      if (t.tag === 30) {
        var e = t.memoizedProps, n = On(e, t.stateNode);
        e = Nn(e.default, e.update), t.flags &= -5, e !== "none" && Ei(
          t,
          n,
          e,
          t.memoizedState = [],
          !1
        );
      } else
        (t.subtreeFlags & 33554432) !== 0 && ry(t);
      t = t.sibling;
    }
  }
  function $r(t) {
    if ((t.subtreeFlags & 18874368) !== 0)
      for (t = t.child; t !== null; ) {
        if (t.tag !== 22 || t.memoizedState === null) {
          if (t.tag === 30 && (t.flags & 18874368) !== 0) {
            var e = t.stateNode;
            e.paired !== null && (e.paired = null, mn(t.child, !1));
          }
          $r(t);
        }
        t = t.sibling;
      }
  }
  function cu(t) {
    if (t.tag === 30)
      t.stateNode.paired = null, mn(t.child, !1), $r(t);
    else if ((t.subtreeFlags & 33554432) !== 0)
      for (t = t.child; t !== null; )
        cu(t), t = t.sibling;
    else $r(t);
  }
  function cy(t) {
    for (t = t.child; t !== null; )
      t.tag === 30 ? mn(t.child, !1) : (t.subtreeFlags & 33554432) !== 0 && cy(t), t = t.sibling;
  }
  function tc(t, e, n, a, s, u, f) {
    for (var m = !1; e !== null; ) {
      if (e.tag === 5) {
        var S = e.stateNode;
        if (u !== null && Ee < u.length) {
          var D = u[Ee], N = _c(S);
          (D.view || N.view) && (m = !0);
          var w;
          if (w = (t.flags & 4) === 0)
            if (N.clip) w = !0;
            else {
              w = D.rect;
              var A = N.rect;
              w = w.y !== A.y || w.x !== A.x || w.height !== A.height || w.width !== A.width;
            }
          w && (t.flags |= 4), N.abs ? N = !D.abs : (D = D.rect, N = N.rect, N = D.height !== N.height || D.width !== N.width), N && (t.flags |= 32);
        } else t.flags |= 32;
        (t.flags & 4) !== 0 && up(
          S,
          Ee === 0 ? n : n + "_" + Ee,
          s
        ), m && (t.flags & 4) !== 0 || (dn === null && (dn = []), dn.push(
          S,
          Ee === 0 ? a : a + "_" + Ee,
          e.memoizedProps
        )), Ee++;
      } else (e.tag !== 22 || e.memoizedState === null) && (e.tag === 30 && f ? t.flags |= e.flags & 32 : tc(
        t,
        e.child,
        n,
        a,
        s,
        u,
        f
      ) && (m = !0));
      e = e.sibling;
    }
    return m;
  }
  function fy(t, e) {
    for (t = t.child; t !== null; ) {
      if (t.tag === 30) {
        var n = t.memoizedProps, a = t.stateNode, s = On(n, a), u = Nn(n.default, n.update), f;
        f = t.memoizedState, t.memoizedState = null, a = t;
        var m = t.child;
        Ee = 0, s = tc(
          a,
          m,
          s,
          s,
          u,
          f,
          !1
        ), (t.flags & 4) !== 0 && s && Ri(t, n.onUpdate);
      } else
        (t.subtreeFlags & 33554432) !== 0 && fy(t);
      t = t.sibling;
    }
  }
  var ee = !1, At = !1, yn = !1, ec = !1, hy = typeof WeakSet == "function" ? WeakSet : Set, ne = null, pn = !1, zl = !1, fu = !1, nc = !1;
  function Bb(t, e, n) {
    if (t = t.containerInfo, Cc = qi, t = pd(t), Go(t)) {
      if ("selectionStart" in t)
        var a = {
          start: t.selectionStart,
          end: t.selectionEnd
        };
      else
        t: {
          a = (a = t.ownerDocument) && a.defaultView || window;
          var s = a.getSelection && a.getSelection();
          if (s && s.rangeCount !== 0) {
            a = s.anchorNode;
            var u = s.anchorOffset, f = s.focusNode;
            s = s.focusOffset;
            try {
              a.nodeType, f.nodeType;
            } catch {
              a = null;
              break t;
            }
            var m = 0, S = -1, D = -1, N = 0, w = 0, A = t, O = null;
            e: for (; ; ) {
              for (var X; A !== a || u !== 0 && A.nodeType !== 3 || (S = m + u), A !== f || s !== 0 && A.nodeType !== 3 || (D = m + s), A.nodeType === 3 && (m += A.nodeValue.length), (X = A.firstChild) !== null; )
                O = A, A = X;
              for (; ; ) {
                if (A === t) break e;
                if (O === a && ++N === u && (S = m), O === f && ++w === s && (D = m), (X = A.nextSibling) !== null) break;
                A = O, O = A.parentNode;
              }
              A = X;
            }
            a = S === -1 || D === -1 ? null : { start: S, end: D };
          } else a = null;
        }
      a = a || { start: 0, end: 0 };
    } else a = null;
    for (Oc = { focusedElem: t, selectionRange: a }, qi = !1, n = (n & 335544064) === n, ne = e, e = n ? 9270 : 1024; ne !== null; ) {
      if (t = ne, n && (a = t.deletions, a !== null))
        for (u = 0; u < a.length; u++)
          n && Ir(a[u]);
      if (t.alternate === null && (t.flags & 2) !== 0)
        n && sy(t), hu(n);
      else {
        if (t.tag === 22) {
          if (a = t.alternate, t.memoizedState !== null) {
            a !== null && a.memoizedState === null && n && Ir(a), hu(n);
            continue;
          } else if (a !== null && a.memoizedState !== null) {
            n && sy(t), hu(n);
            continue;
          }
        }
        a = t.child, (t.subtreeFlags & e) !== 0 && a !== null ? (a.return = t, ne = a) : (n && ry(t), hu(n));
      }
    }
    we = null;
  }
  function hu(t) {
    for (; ne !== null; ) {
      var e = ne, n = t, a = e.alternate, s = e.flags;
      switch (e.tag) {
        case 0:
        case 11:
        case 15:
          break;
        case 1:
          if ((s & 1024) !== 0 && a !== null) {
            n = void 0, s = a.memoizedProps, a = a.memoizedState;
            var u = e.stateNode;
            try {
              var f = La(
                e.type,
                s
              );
              n = u.getSnapshotBeforeUpdate(
                f,
                a
              ), u.__reactInternalSnapshotBeforeUpdate = n;
            } catch (m) {
              Dt(e, e.return, m);
            }
          }
          break;
        case 3:
          if ((s & 1024) !== 0) {
            if (a = e.stateNode.containerInfo, n = a.nodeType, n === 9)
              jc(a);
            else if (n === 1)
              switch (a.nodeName) {
                case "HEAD":
                case "HTML":
                case "BODY":
                  jc(a);
                  break;
                default:
                  a.textContent = "";
              }
          }
          break;
        case 5:
        case 26:
        case 27:
        case 6:
        case 4:
        case 17:
          break;
        case 30:
          n && a !== null && (n = On(
            a.memoizedProps,
            a.stateNode
          ), s = e.memoizedProps, s = Nn(s.default, s.update), s !== "none" && Ei(
            a,
            n,
            s,
            a.memoizedState = [],
            !0
          ));
          break;
        default:
          if ((s & 1024) !== 0) throw Error(o(163));
      }
      if (a = e.sibling, a !== null) {
        a.return = e.return, ne = a;
        break;
      }
      ne = e.return;
    }
  }
  function dy(t, e, n) {
    var a = n.flags;
    switch (n.tag) {
      case 0:
      case 11:
      case 15:
        gn(t, n), a & 4 && Ol(5, n);
        break;
      case 1:
        if (gn(t, n), a & 4)
          if (t = n.stateNode, e === null)
            try {
              t.componentDidMount();
            } catch (f) {
              Dt(n, n.return, f);
            }
          else {
            var s = La(
              n.type,
              e.memoizedProps
            );
            e = e.memoizedState;
            try {
              t.componentDidUpdate(
                s,
                e,
                t.__reactInternalSnapshotBeforeUpdate
              );
            } catch (f) {
              Dt(
                n,
                n.return,
                f
              );
            }
          }
        a & 64 && ey(n), a & 512 && hn(n, n.return);
        break;
      case 3:
        if (gn(t, n), a & 64 && (t = n.updateQueue, t !== null)) {
          if (e = null, n.child !== null)
            switch (n.child.tag) {
              case 27:
              case 5:
                e = n.child.stateNode;
                break;
              case 1:
                e = n.child.stateNode;
            }
          try {
            Qd(t, e);
          } catch (f) {
            Dt(n, n.return, f);
          }
        }
        break;
      case 27:
        e === null && a & 4 && ly(n);
      case 26:
      case 5:
        gn(t, n), e === null && a & 4 && Kr(n), a & 512 && hn(n, n.return);
        break;
      case 12:
        gn(t, n);
        break;
      case 31:
        gn(t, n), a & 4 && gy(t, n);
        break;
      case 13:
        gn(t, n), a & 4 && vy(t, n), a & 64 && (t = n.memoizedState, t !== null && (t = t.dehydrated, t !== null && (n = Pb.bind(
          null,
          n
        ), zS(t, n))));
        break;
      case 22:
        if (a = n.memoizedState !== null || ee, !a) {
          var u = e !== null && e.memoizedState !== null || At;
          e = ee, s = At, ee = a, (At = u) && !s ? (a = 2, (n.subtreeFlags & 8772) !== 0 && (a |= 1), tn(
            t,
            n,
            a
          )) : gn(t, n), ee = e, At = s;
        }
        break;
      case 30:
        gn(t, n), a & 512 && hn(n, n.return);
        break;
      case 7:
        a & 512 && hn(n, n.return);
      default:
        gn(t, n);
    }
  }
  function ac(t, e) {
    for (t = t.child; t !== null; )
      my(t, e), t = t.sibling;
  }
  function my(t, e) {
    switch (t.tag) {
      case 5:
      case 26:
        try {
          var n = t.stateNode;
          if (e) {
            var a = n.style;
            typeof a.setProperty == "function" ? a.setProperty("display", "none", "important") : a.display = "none";
          } else {
            var s = t.stateNode, u = t.memoizedProps.style, f = u != null && u.hasOwnProperty("display") ? u.display : null;
            s.style.display = f == null || typeof f == "boolean" ? "" : ("" + f).trim();
          }
        } catch (S) {
          Dt(t, t.return, S);
        }
        ic(t, e);
        break;
      case 6:
        try {
          t.stateNode.nodeValue = e ? "" : t.memoizedProps, Tt = !0;
        } catch (S) {
          Dt(t, t.return, S);
        }
        break;
      case 18:
        try {
          var m = t.stateNode;
          e ? sp(m, !0) : sp(t.stateNode, !1);
        } catch (S) {
          Dt(t, t.return, S);
        }
        break;
      case 22:
      case 23:
        t.memoizedState === null && ac(t, e);
        break;
      default:
        ac(t, e);
    }
  }
  function ic(t, e) {
    if (t.subtreeFlags & 67108864)
      for (t = t.child; t !== null; ) {
        t: {
          var n = t, a = e;
          switch (n.tag) {
            case 4:
              my(n, a);
              break t;
            case 22:
              n.memoizedState === null && ic(n, a);
              break t;
            default:
              ic(n, a);
          }
        }
        t = t.sibling;
      }
  }
  function yy(t) {
    var e = t.alternate;
    e !== null && (t.alternate = null, yy(e)), t.child = null, t.deletions = null, t.sibling = null, t.tag === 5 && (e = t.stateNode, e !== null && gs(e)), t.stateNode = null, t.return = null, t.dependencies = null, t.memoizedProps = null, t.memoizedState = null, t.pendingProps = null, t.stateNode = null, t.updateQueue = null;
  }
  var Ht = null, Ae = !1;
  function Ie(t, e, n) {
    for (n = n.child; n !== null; )
      py(t, e, n), n = n.sibling;
  }
  function py(t, e, n) {
    if (Oe && typeof Oe.onCommitFiberUnmount == "function")
      try {
        Oe.onCommitFiberUnmount($i, n);
      } catch {
      }
    switch (n.tag) {
      case 26:
        At || oe(n, e), Ie(
          t,
          e,
          n
        ), n.memoizedState ? n.memoizedState.count-- : n.stateNode && !At && (n = n.stateNode, n.parentNode.removeChild(n));
        break;
      case 27:
        At || oe(n, e), Nl(n);
        var a = Ht, s = Ae;
        ca(n.type) && (Ht = n.stateNode, Ae = !1), Ie(
          t,
          e,
          n
        ), Sp(
          n.stateNode,
          n.type,
          n.memoizedProps
        ), Ht = a, Ae = s;
        break;
      case 5:
        At || oe(n, e), Nl(n);
      case 6:
        if (n.tag === 6 && Nl(n), a = Ht, s = Ae, Ht = null, Ie(
          t,
          e,
          n
        ), Ht = a, Ae = s, Ht !== null)
          if (Ae)
            try {
              (Ht.nodeType === 9 ? Ht.body : Ht.nodeName === "HTML" ? Ht.ownerDocument.body : Ht).removeChild(n.stateNode), Tt = !0;
            } catch (u) {
              Dt(
                n,
                e,
                u
              );
            }
          else
            try {
              Ht.removeChild(n.stateNode), Tt = !0;
            } catch (u) {
              Dt(
                n,
                e,
                u
              );
            }
        break;
      case 18:
        Ht !== null && (Ae ? (t = Ht, lp(
          t.nodeType === 9 ? t.body : t.nodeName === "HTML" ? t.ownerDocument.body : t,
          n.stateNode
        ), Gi(t)) : lp(Ht, n.stateNode));
        break;
      case 4:
        a = Ht, s = Ae, Ht = n.stateNode.containerInfo, Ae = !0, Ie(
          t,
          e,
          n
        ), Ht = a, Ae = s;
        break;
      case 0:
      case 11:
      case 14:
      case 15:
        aa(2, n, e), At || aa(4, n, e), Ie(
          t,
          e,
          n
        );
        break;
      case 1:
        At || (oe(n, e), a = n.stateNode, typeof a.componentWillUnmount == "function" && ny(
          n,
          e,
          a
        )), Ie(
          t,
          e,
          n
        );
        break;
      case 21:
        Ie(
          t,
          e,
          n
        );
        break;
      case 22:
        At = (a = At) || n.memoizedState !== null, Ie(
          t,
          e,
          n
        ), At = a;
        break;
      case 30:
        oe(n, e), Ie(
          t,
          e,
          n
        );
        break;
      case 7:
        At || oe(n, e), Ie(
          t,
          e,
          n
        );
        break;
      default:
        Ie(
          t,
          e,
          n
        );
    }
  }
  function gy(t, e) {
    if (e.memoizedState === null && (t = e.alternate, t !== null && (t = t.memoizedState, t !== null))) {
      t = t.dehydrated;
      try {
        Gi(t);
      } catch (n) {
        Dt(e, e.return, n);
      }
    }
  }
  function vy(t, e) {
    if (e.memoizedState === null && (t = e.alternate, t !== null && (t = t.memoizedState, t !== null && (t = t.dehydrated, t !== null))))
      try {
        Gi(t);
      } catch (n) {
        Dt(e, e.return, n);
      }
  }
  function Hb(t) {
    switch (t.tag) {
      case 31:
      case 13:
      case 19:
        var e = t.stateNode;
        return e === null && (e = t.stateNode = new hy()), e;
      case 22:
        return t = t.stateNode, e = t._retryCache, e === null && (e = t._retryCache = new hy()), e;
      default:
        throw Error(o(435, t.tag));
    }
  }
  function du(t, e) {
    var n = Hb(t);
    e.forEach(function(a) {
      if (!n.has(a)) {
        n.add(a);
        var s = Fb.bind(null, t, a);
        a.then(s, s);
      }
    });
  }
  function ge(t, e, n) {
    var a = e.deletions;
    if (a !== null)
      for (var s = 0; s < a.length; s++) {
        var u = a[s], f = t, m = e, S = m;
        t: for (; S !== null; ) {
          switch (S.tag) {
            case 27:
              if (ca(S.type)) {
                Ht = S.stateNode, Ae = !1;
                break t;
              }
              break;
            case 5:
              Ht = S.stateNode, Ae = !1;
              break t;
            case 3:
            case 4:
              Ht = S.stateNode.containerInfo, Ae = !0;
              break t;
          }
          S = S.return;
        }
        if (Ht === null) throw Error(o(160));
        py(f, m, u), Ht = null, Ae = !1, f = u.alternate, f !== null && (f.return = null), u.return = null;
      }
    if (e.subtreeFlags & 13886)
      for (e = e.child; e !== null; )
        by(e, t, n), e = e.sibling;
  }
  var $e = null;
  function by(t, e, n) {
    var a = t.alternate, s = t.flags;
    switch (t.tag) {
      case 0:
      case 11:
      case 14:
      case 15:
        if (s & 4 && (a = t.updateQueue, a = a !== null ? a.events : null, a !== null))
          for (var u = 0; u < a.length; u++) {
            var f = a[u];
            f.ref.impl = f.nextImpl;
          }
        ge(e, t, n), ve(t), s & 4 && (aa(3, t, t.return), Ol(3, t), aa(5, t, t.return));
        break;
      case 1:
        ge(e, t, n), ve(t), s & 512 && (At || a === null || oe(a, a.return)), s & 64 && ee && (t = t.updateQueue, t !== null && (e = t.callbacks, e !== null && (n = t.shared.hiddenCallbacks, t.shared.hiddenCallbacks = n === null ? e : n.concat(e))));
        break;
      case 26:
        if (u = $e, ge(e, t, n), ve(t), s & 512 && (At || a === null || oe(a, a.return)), s & 4)
          if (s = a !== null ? a.memoizedState : null, n = t.memoizedState, a === null)
            if (n === null)
              if (t.stateNode === null)
                if (ee)
                  t.stateNode = np(
                    t.type,
                    t.memoizedProps,
                    e.containerInfo,
                    t
                  );
                else {
                  t: {
                    e = t.type, n = t.memoizedProps, s = u.ownerDocument || u;
                    e: switch (e) {
                      case "title":
                        a = s.getElementsByTagName("title")[0], (!a || a[nl] || a[ie] || a.namespaceURI === "http://www.w3.org/2000/svg" || a.hasAttribute("itemprop")) && (a = s.createElement(e), s.head.insertBefore(
                          a,
                          s.querySelector("head > title")
                        )), re(a, e, n), a[ie] = t, $t(a), e = a;
                        break t;
                      case "link":
                        if (u = Dp(
                          "link",
                          "href",
                          s
                        ).get(e + (n.href || ""))) {
                          for (f = 0; f < u.length; f++)
                            if (a = u[f], a.getAttribute("href") === (n.href == null || n.href === "" ? null : n.href) && a.getAttribute("rel") === (n.rel == null ? null : n.rel) && a.getAttribute("title") === (n.title == null ? null : n.title) && a.getAttribute("crossorigin") === (n.crossOrigin == null ? null : n.crossOrigin)) {
                              u.splice(f, 1);
                              break e;
                            }
                        }
                        a = s.createElement(e), re(a, e, n), s.head.appendChild(a);
                        break;
                      case "meta":
                        if (u = Dp(
                          "meta",
                          "content",
                          s
                        ).get(e + (n.content || ""))) {
                          for (f = 0; f < u.length; f++)
                            if (a = u[f], a.getAttribute("content") === (n.content == null ? null : "" + n.content) && a.getAttribute("name") === (n.name == null ? null : n.name) && a.getAttribute("property") === (n.property == null ? null : n.property) && a.getAttribute("http-equiv") === (n.httpEquiv == null ? null : n.httpEquiv) && a.getAttribute("charset") === (n.charSet == null ? null : n.charSet)) {
                              u.splice(f, 1);
                              break e;
                            }
                        }
                        a = s.createElement(e), re(a, e, n), s.head.appendChild(a);
                        break;
                      default:
                        throw Error(o(468, e));
                    }
                    a[ie] = t, $t(a), e = a;
                  }
                  t.stateNode = e;
                }
              else
                ee || Gc(u, t.type, t.stateNode);
            else
              t.stateNode = Mp(
                u,
                n,
                t.memoizedProps
              );
          else
            s !== n ? (s === null ? (e = a.stateNode, e === null || At || e.parentNode.removeChild(e)) : s.count--, n === null ? ee || Gc(u, t.type, t.stateNode) : Mp(u, n, t.memoizedProps)) : n === null && t.stateNode !== null && Jr(
              t,
              t.memoizedProps,
              a.memoizedProps
            );
        break;
      case 27:
        ge(e, t, n), ve(t), s & 512 && (At || a === null || oe(a, a.return)), a !== null && s & 4 && Jr(
          t,
          t.memoizedProps,
          a.memoizedProps
        );
        break;
      case 5:
        if (u = yn, yn = !1, ge(e, t, n), yn = u, ve(t), s & 512 && (At || a === null || oe(a, a.return)), t.flags & 32) {
          e = t.stateNode;
          try {
            li(e, ""), Tt = !0;
          } catch (N) {
            Dt(t, t.return, N);
          }
        }
        s & 4 && t.stateNode != null && (e = t.memoizedProps, Jr(
          t,
          e,
          a !== null ? a.memoizedProps : e
        )), s & 1024 && (ec = !0);
        break;
      case 6:
        if (ge(e, t, n), ve(t), s & 4) {
          if (t.stateNode === null)
            throw Error(o(162));
          e = t.memoizedProps, n = t.stateNode;
          try {
            n.nodeValue = e, Tt = !0;
          } catch (N) {
            Dt(t, t.return, N);
          }
        }
        break;
      case 3:
        if (Tt = !1, Ou = null, u = $e, $e = Ll(e.containerInfo), ge(e, t, n), $e = u, ve(t), s & 4 && a !== null && a.memoizedState.isDehydrated)
          try {
            Gi(e.containerInfo);
          } catch (N) {
            Dt(t, t.return, N);
          }
        ec && (ec = !1, Sy(t)), Tt = !1;
        break;
      case 4:
        s = yn, yn = ee, a = Yh(), u = $e, $e = Ll(
          t.stateNode.containerInfo
        ), ge(e, t, n), ve(t), $e = u, Tt && zl && (fu = !0), Tt = a, yn = s;
        break;
      case 12:
        ge(e, t, n), ve(t);
        break;
      case 31:
        ge(e, t, n), ve(t), s & 4 && (e = t.updateQueue, e !== null && (t.updateQueue = null, du(t, e)));
        break;
      case 13:
        ge(e, t, n), ve(t), t.child.flags & 8192 && t.memoizedState !== null != (a !== null && a.memoizedState !== null) && (pu = Ce()), s & 4 && (e = t.updateQueue, e !== null && (t.updateQueue = null, du(t, e)));
        break;
      case 22:
        u = t.memoizedState !== null, f = a !== null && a.memoizedState !== null;
        var m = ee, S = At, D = yn;
        ee = m || u, yn = D || u, At = S || f, ge(e, t, n), At = S, yn = D, ee = m, ve(t), s & 8192 && (e = t.stateNode, e._visibility = u ? e._visibility & -2 : e._visibility | 1, !u || a === null || f || ee || At || (e = f || At, n = ee, a = At, ee = u || ee, At = e, ia(t, 2), ee = n, At = a), !u && yn || ac(t, u)), s & 4 && (e = t.updateQueue, e !== null && (n = e.retryQueue, n !== null && (e.retryQueue = null, du(t, n))));
        break;
      case 19:
        ge(e, t, n), ve(t), s & 4 && (e = t.updateQueue, e !== null && (t.updateQueue = null, du(t, e)));
        break;
      case 30:
        s & 512 && (At || a === null || oe(a, a.return)), s = Yh(), u = zl, f = (n & 335544064) === n, m = t.memoizedProps, zl = f && Nn(
          m.default,
          m.update
        ) !== "none", ge(e, t, n), ve(t), f && a !== null && Tt && (t.flags |= 4), zl = u, Tt = s;
        break;
      case 21:
        break;
      case 7:
        s & 512 && (At || a === null || oe(a, a.return)), a && a.stateNode !== null && (a.stateNode._fragmentFiber = t);
      default:
        ge(e, t, n), ve(t);
    }
  }
  function ve(t) {
    var e = t.flags;
    if (e & 2) {
      try {
        for (var n, a = t.return; a !== null; ) {
          if (iy(a)) {
            n = a;
            break;
          }
          a = a.return;
        }
        a = null;
        for (var s = t.return; s !== null; ) {
          if (Zr(s)) {
            var u = s.stateNode;
            a === null ? a = [u] : a.push(u);
          }
          if (Qr(s)) break;
          s = s.return;
        }
        var f = a;
        if (n == null) throw Error(o(160));
        switch (n.tag) {
          case 27:
            var m = n.stateNode, S = kr(t);
            uu(
              t,
              S,
              m,
              f
            );
            break;
          case 5:
            var D = n.stateNode;
            n.flags & 32 && (li(D, ""), n.flags &= -33);
            var N = kr(t);
            uu(
              t,
              N,
              D,
              f
            );
            break;
          case 3:
          case 4:
            var w = n.stateNode.containerInfo, A = kr(t);
            Pr(
              t,
              A,
              w,
              f
            );
            break;
          default:
            throw Error(o(161));
        }
      } catch (O) {
        Dt(t, t.return, O);
      }
      t.flags &= -3;
    }
    e & 4096 && (t.flags &= -4097);
  }
  function Sy(t) {
    if (t.subtreeFlags & 1024)
      for (t = t.child; t !== null; ) {
        var e = t;
        Sy(e), e.tag === 5 && e.flags & 1024 && (e = e.stateNode, qi = !0, e.reset(), qi = !1), t = t.sibling;
      }
  }
  function Ai(t, e) {
    if (e.subtreeFlags & 9270)
      for (e = e.child; e !== null; )
        Ty(e, t), e = e.sibling;
    else fy(e);
  }
  function Ty(t, e) {
    var n = t.alternate;
    if (n === null) Fr(t, !1);
    else
      switch (t.tag) {
        case 3:
          if (nc = pn = !1, uy(), Ai(e, t), !pn && !fu) {
            if (t = dn, t !== null)
              for (var a = 0; a < t.length; a += 3) {
                n = t[a];
                var s = t[a + 1];
                op(n, t[a + 2]), n = n.ownerDocument.documentElement, n !== null && n.animate(
                  { opacity: [0, 0], pointerEvents: ["none", "none"] },
                  {
                    duration: 0,
                    fill: "forwards",
                    pseudoElement: "::view-transition-group(" + s + ")"
                  }
                );
              }
            t = e.containerInfo, t = t.nodeType === 9 ? t.documentElement : t.ownerDocument.documentElement, t !== null && t.style.viewTransitionName === "" && (t.style.viewTransitionName = "none", t.animate(
              { opacity: [0, 0], pointerEvents: ["none", "none"] },
              {
                duration: 0,
                fill: "forwards",
                pseudoElement: "::view-transition-group(root)"
              }
            ), t.animate(
              { width: [0, 0], height: [0, 0] },
              {
                duration: 0,
                fill: "forwards",
                pseudoElement: "::view-transition"
              }
            )), nc = !0;
          }
          dn = null;
          break;
        case 5:
          Ai(e, t);
          break;
        case 4:
          a = pn, pn = !1, Ai(e, t), pn && (fu = !0), pn = a;
          break;
        case 22:
          t.memoizedState === null && (n.memoizedState !== null ? Fr(t, !1) : Ai(e, t));
          break;
        case 30:
          a = pn, s = uy(), pn = !1, Ai(e, t), pn && (t.flags |= 4);
          var u = t.memoizedProps, f = t.stateNode;
          e = On(u, f), f = On(n.memoizedProps, f);
          var m = Nn(u.default, u.update);
          m === "none" ? e = !1 : (u = n.memoizedState, n.memoizedState = null, n = t.child, Ee = 0, e = tc(
            t,
            n,
            e,
            f,
            m,
            u,
            !0
          ), Ee !== (u === null ? 0 : u.length) && (t.flags |= 32)), (t.flags & 4) !== 0 && e ? (Ri(
            t,
            t.memoizedProps.onUpdate
          ), dn = s) : s !== null && (s.push.apply(s, dn), dn = s), pn = (t.flags & 32) !== 0 ? !0 : a;
          break;
        default:
          Ai(e, t);
      }
  }
  function gn(t, e) {
    if (e.subtreeFlags & 8772)
      for (e = e.child; e !== null; )
        dy(t, e.alternate, e), e = e.sibling;
  }
  function ia(t, e) {
    for (t = t.child; t !== null; ) {
      var n = t, a = e;
      switch (n.tag) {
        case 0:
        case 11:
        case 14:
        case 15:
          aa(4, n, n.return), ia(
            n,
            a
          );
          break;
        case 1:
          oe(n, n.return);
          var s = n.stateNode;
          typeof s.componentWillUnmount == "function" && ny(
            n,
            n.return,
            s
          ), ia(
            n,
            a
          );
          break;
        case 27:
          (a & 2) !== 0 && Sp(
            n.stateNode,
            n.type,
            n.memoizedProps
          );
        case 5:
          oe(n, n.return), n.tag !== 5 && n.tag !== 27 || Nl(n), ia(
            n,
            a
          );
          break;
        case 6:
          Nl(n);
          break;
        case 26:
          oe(n, n.return), s = n.stateNode, n.memoizedState !== null || s === null || At || s.parentNode.removeChild(s), ia(
            n,
            a
          );
          break;
        case 22:
          n.memoizedState === null && ia(
            n,
            a
          );
          break;
        case 30:
          oe(n, n.return), ia(
            n,
            a
          );
          break;
        case 7:
          oe(n, n.return);
        default:
          ia(
            n,
            a
          );
      }
      t = t.sibling;
    }
  }
  function tn(t, e, n) {
    for (n = (e.subtreeFlags & 8772) !== 0 ? n : n & -2, e = e.child; e !== null; ) {
      var a = e.alternate, s = t, u = e, f = u.flags, m = (n & 1) !== 0;
      switch (u.tag) {
        case 0:
        case 11:
        case 15:
          tn(
            s,
            u,
            n
          ), Ol(4, u);
          break;
        case 1:
          if (tn(
            s,
            u,
            n
          ), a = u, s = a.stateNode, typeof s.componentDidMount == "function")
            try {
              s.componentDidMount();
            } catch (N) {
              Dt(a, a.return, N);
            }
          if (a = u, s = a.updateQueue, s !== null) {
            var S = a.stateNode;
            try {
              var D = s.shared.hiddenCallbacks;
              if (D !== null)
                for (s.shared.hiddenCallbacks = null, s = 0; s < D.length; s++)
                  Xd(D[s], S);
            } catch (N) {
              Dt(a, a.return, N);
            }
          }
          m && f & 64 && ey(u), hn(u, u.return);
          break;
        case 27:
          (n & 2) !== 0 && ly(u);
        case 5:
          u.tag !== 5 && u.tag !== 27 || ay(u), tn(
            s,
            u,
            n
          ), m && a === null && f & 4 && Kr(u), hn(u, u.return);
          break;
        case 6:
          ay(u);
          break;
        case 26:
          S = u.stateNode, u.memoizedState !== null || S === null || ee || Gc(
            Ll(S.ownerDocument),
            u.type,
            S
          ), tn(
            s,
            u,
            n
          ), m && a === null && f & 4 && Kr(u), hn(u, u.return);
          break;
        case 12:
          tn(
            s,
            u,
            n
          );
          break;
        case 31:
          tn(
            s,
            u,
            n
          ), m && f & 4 && gy(s, u);
          break;
        case 13:
          tn(
            s,
            u,
            n
          ), m && f & 4 && vy(s, u);
          break;
        case 22:
          u.memoizedState === null && tn(
            s,
            u,
            n
          ), hn(u, u.return);
          break;
        case 30:
          tn(
            s,
            u,
            n
          ), hn(u, u.return);
          break;
        case 7:
          hn(u, u.return);
        default:
          tn(
            s,
            u,
            n
          );
      }
      e = e.sibling;
    }
  }
  function lc(t, e) {
    var n = null;
    t !== null && t.memoizedState !== null && t.memoizedState.cachePool !== null && (n = t.memoizedState.cachePool.pool), t = null, e.memoizedState !== null && e.memoizedState.cachePool !== null && (t = e.memoizedState.cachePool.pool), t !== n && (t != null && t.refCount++, n != null && yl(n));
  }
  function sc(t, e) {
    t = null, e.alternate !== null && (t = e.alternate.memoizedState.cache), e = e.memoizedState.cache, e !== t && (e.refCount++, t != null && yl(t));
  }
  function Ze(t, e, n, a) {
    var s = (n & 335544064) === n;
    if (e.subtreeFlags & (s ? 10262 : 10256))
      for (e = e.child; e !== null; )
        xy(
          t,
          e,
          n,
          a
        ), e = e.sibling;
    else s && cy(e);
  }
  function xy(t, e, n, a) {
    var s = (n & 335544064) === n;
    s && e.alternate === null && e.return !== null && e.return.alternate !== null && cu(e);
    var u = e.flags;
    switch (e.tag) {
      case 0:
      case 11:
      case 15:
        Ze(
          t,
          e,
          n,
          a
        ), u & 2048 && Ol(9, e);
        break;
      case 1:
        Ze(
          t,
          e,
          n,
          a
        );
        break;
      case 3:
        Ze(
          t,
          e,
          n,
          a
        ), s && nc && (t = t.containerInfo, t = t.nodeType === 9 ? t.body : t.nodeName === "HTML" ? t.ownerDocument.body : t, t.style.viewTransitionName === "root" && (t.style.viewTransitionName = ""), t = t.ownerDocument.documentElement, t !== null && t.style.viewTransitionName === "none" && (t.style.viewTransitionName = "")), u & 2048 && (u = null, e.alternate !== null && (u = e.alternate.memoizedState.cache), e = e.memoizedState.cache, e !== u && (e.refCount++, u != null && yl(u)));
        break;
      case 12:
        if (u & 2048) {
          Ze(
            t,
            e,
            n,
            a
          ), u = e.stateNode;
          try {
            var f = e.memoizedProps, m = f.id, S = f.onPostCommit;
            typeof S == "function" && S(
              m,
              e.alternate === null ? "mount" : "update",
              u.passiveEffectDuration,
              -0
            );
          } catch (D) {
            Dt(e, e.return, D);
          }
        } else
          Ze(
            t,
            e,
            n,
            a
          );
        break;
      case 31:
        Ze(
          t,
          e,
          n,
          a
        );
        break;
      case 13:
        Ze(
          t,
          e,
          n,
          a
        );
        break;
      case 23:
        break;
      case 22:
        f = e.stateNode, m = e.alternate, e.memoizedState !== null ? (s && m !== null && m.memoizedState === null && cu(m), f._visibility & 2 ? Ze(
          t,
          e,
          n,
          a
        ) : Rl(
          t,
          e
        )) : (s && m !== null && m.memoizedState !== null && cu(e), f._visibility & 2 ? Ze(
          t,
          e,
          n,
          a
        ) : (f._visibility |= 2, Mi(
          t,
          e,
          n,
          a,
          (e.subtreeFlags & 10256) !== 0 || !1
        ))), u & 2048 && lc(m, e);
        break;
      case 24:
        Ze(
          t,
          e,
          n,
          a
        ), u & 2048 && sc(e.alternate, e);
        break;
      case 30:
        s && (u = e.alternate, u !== null && (mn(u.child, !0), mn(e.child, !0))), Ze(
          t,
          e,
          n,
          a
        );
        break;
      default:
        Ze(
          t,
          e,
          n,
          a
        );
    }
  }
  function Mi(t, e, n, a, s) {
    for (s = s && ((e.subtreeFlags & 10256) !== 0 || !1), e = e.child; e !== null; ) {
      var u = t, f = e, m = n, S = a, D = f.flags;
      switch (f.tag) {
        case 0:
        case 11:
        case 15:
          Mi(
            u,
            f,
            m,
            S,
            s
          ), Ol(8, f);
          break;
        case 23:
          break;
        case 22:
          var N = f.stateNode;
          f.memoizedState !== null ? N._visibility & 2 ? Mi(
            u,
            f,
            m,
            S,
            s
          ) : Rl(
            u,
            f
          ) : (N._visibility |= 2, Mi(
            u,
            f,
            m,
            S,
            s
          )), s && D & 2048 && lc(
            f.alternate,
            f
          );
          break;
        case 24:
          Mi(
            u,
            f,
            m,
            S,
            s
          ), s && D & 2048 && sc(f.alternate, f);
          break;
        default:
          Mi(
            u,
            f,
            m,
            S,
            s
          );
      }
      e = e.sibling;
    }
  }
  function Rl(t, e) {
    if (e.subtreeFlags & 10256)
      for (e = e.child; e !== null; ) {
        var n = t, a = e, s = a.flags;
        switch (a.tag) {
          case 22:
            Rl(n, a), s & 2048 && lc(
              a.alternate,
              a
            );
            break;
          case 24:
            Rl(n, a), s & 2048 && sc(a.alternate, a);
            break;
          default:
            Rl(n, a);
        }
        e = e.sibling;
      }
  }
  var Ya = 8192;
  function qa(t, e, n) {
    if (t.subtreeFlags & Ya)
      for (t = t.child; t !== null; )
        Ey(
          t,
          e,
          n
        ), t = t.sibling;
  }
  function Ey(t, e, n) {
    switch (t.tag) {
      case 26:
        qa(
          t,
          e,
          n
        ), t.flags & Ya && (t.memoizedState !== null ? QS(
          n,
          $e,
          t.memoizedState,
          t.memoizedProps
        ) : (t = t.stateNode, (e & 335544128) === e && zp(n, t)));
        break;
      case 5:
        qa(
          t,
          e,
          n
        ), t.flags & Ya && (t = t.stateNode, (e & 335544128) === e && zp(n, t));
        break;
      case 3:
      case 4:
        var a = $e;
        $e = Ll(t.stateNode.containerInfo), qa(
          t,
          e,
          n
        ), $e = a;
        break;
      case 22:
        t.memoizedState === null && (a = t.alternate, a !== null && a.memoizedState !== null ? (a = Ya, Ya = 16777216, qa(
          t,
          e,
          n
        ), Ya = a) : qa(
          t,
          e,
          n
        ));
        break;
      case 30:
        if ((t.flags & Ya) !== 0 && (a = t.memoizedProps.name, a != null && a !== "auto")) {
          var s = t.stateNode;
          s.paired = null, we === null && (we = /* @__PURE__ */ new Map()), we.set(a, s);
        }
        qa(
          t,
          e,
          n
        );
        break;
      default:
        qa(
          t,
          e,
          n
        );
    }
  }
  function Ay(t) {
    var e = t.alternate;
    if (e !== null && (t = e.child, t !== null)) {
      e.child = null;
      do
        e = t.sibling, t.sibling = null, t = e;
      while (t !== null);
    }
  }
  function _l(t) {
    var e = t.deletions;
    if ((t.flags & 16) !== 0) {
      if (e !== null)
        for (var n = 0; n < e.length; n++) {
          var a = e[n];
          ne = a, Dy(
            a,
            t
          );
        }
      Ay(t);
    }
    if (t.subtreeFlags & 10256)
      for (t = t.child; t !== null; )
        My(t), t = t.sibling;
  }
  function My(t) {
    switch (t.tag) {
      case 0:
      case 11:
      case 15:
        _l(t), t.flags & 2048 && aa(9, t, t.return);
        break;
      case 3:
        _l(t);
        break;
      case 12:
        _l(t);
        break;
      case 22:
        var e = t.stateNode;
        t.memoizedState !== null && e._visibility & 2 && (t.return === null || t.return.tag !== 13) ? (e._visibility &= -3, mu(t)) : _l(t);
        break;
      default:
        _l(t);
    }
  }
  function mu(t) {
    var e = t.deletions;
    if ((t.flags & 16) !== 0) {
      if (e !== null)
        for (var n = 0; n < e.length; n++) {
          var a = e[n];
          ne = a, Dy(
            a,
            t
          );
        }
      Ay(t);
    }
    for (t = t.child; t !== null; ) {
      switch (e = t, e.tag) {
        case 0:
        case 11:
        case 15:
          aa(8, e, e.return), mu(e);
          break;
        case 22:
          n = e.stateNode, n._visibility & 2 && (n._visibility &= -3, mu(e));
          break;
        default:
          mu(e);
      }
      t = t.sibling;
    }
  }
  function Dy(t, e) {
    for (; ne !== null; ) {
      var n = ne;
      switch (n.tag) {
        case 0:
        case 11:
        case 15:
          aa(8, n, e);
          break;
        case 23:
        case 22:
          if (n.memoizedState !== null && n.memoizedState.cachePool !== null) {
            var a = n.memoizedState.cachePool.pool;
            a != null && a.refCount++;
          }
          break;
        case 24:
          yl(n.memoizedState.cache);
      }
      if (a = n.child, a !== null) a.return = n, ne = a;
      else
        t: for (n = t; ne !== null; ) {
          a = ne;
          var s = a.sibling, u = a.return;
          if (yy(a), a === n) {
            ne = null;
            break t;
          }
          if (s !== null) {
            s.return = u, ne = s;
            break t;
          }
          ne = u;
        }
    }
  }
  var Lb = {
    getCacheForType: function(t) {
      var e = le(Qt), n = e.data.get(t);
      return n === void 0 && (n = t(), e.data.set(t, n)), n;
    },
    cacheSignal: function() {
      return le(Qt).controller.signal;
    }
  }, Yb = typeof WeakMap == "function" ? WeakMap : Map, Et = 0, _t = null, dt = null, yt = 0, Mt = 0, Ve = null, la = !1, Di = !1, uc = !1, Hn = 0, qt = 0, sa = 0, Ga = 0, yu = 0, je = 0, Ci = 0, wl = null, Me = null, oc = !1, pu = 0, Cy = 0, gu = 1 / 0, vu = null, ua = null, Lt = 0, en = null, Xa = null, vn = 0, rc = 0, cc = null, Oy = null, Oi = null, Ni = null, zi = null, Vl = 0, bu = null;
  function Ue() {
    return (Et & 2) !== 0 && yt !== 0 ? yt & -yt : W.T !== null ? Sc() : Rh();
  }
  function Ny() {
    if (je === 0)
      if ((yt & 536870912) === 0 || ft) {
        var t = ds;
        ds <<= 1, (ds & 3932160) === 0 && (ds = 262144), je = t;
      } else je = 536870912;
    return t = se.current, t !== null && (t.flags |= 32), je;
  }
  function Ri(t, e) {
    if (e != null) {
      var n = t.stateNode, a = n.ref;
      a === null && (a = n.ref = rp(
        On(t.memoizedProps, n)
      )), Ni === null && (Ni = []), Ni.push(e.bind(null, a));
    }
  }
  function De(t, e, n) {
    (t === _t && (Mt === 2 || Mt === 9) || t.cancelPendingCommit !== null) && (_i(t, 0), oa(
      t,
      yt,
      je,
      !1
    )), el(t, n), ((Et & 2) === 0 || t !== _t) && (t === _t && ((Et & 2) === 0 && (Ga |= n), qt === 4 && oa(
      t,
      yt,
      je,
      !1
    )), bn(t));
  }
  function zy(t, e, n) {
    if ((Et & 6) !== 0) throw Error(o(327));
    var a = !n && (e & 127) === 0 && (e & t.expiredLanes) === 0 || tl(t, e), s = a ? Xb(t, e) : hc(t, e, !0), u = a;
    do {
      if (s === 0) {
        Di && !a && oa(t, e, 0, !1);
        break;
      } else {
        if (n = t.current.alternate, u && !qb(n)) {
          s = hc(t, e, !1), u = !1;
          continue;
        }
        if (s === 2) {
          if (u = e, t.errorRecoveryDisabledLanes & u)
            var f = 0;
          else
            f = t.pendingLanes & -536870913, f = f !== 0 ? f : f & 536870912 ? 536870912 : 0;
          if (f !== 0) {
            e = f;
            t: {
              var m = t;
              s = wl;
              var S = m.current.memoizedState.isDehydrated;
              if (S && (_i(m, f).flags |= 256), f = hc(
                m,
                f,
                !1
              ), f !== 2 && f !== 6) {
                if (uc && !S) {
                  m.errorRecoveryDisabledLanes |= u, Ga |= u, s = 4;
                  break t;
                }
                u = Me, Me = s, u !== null && (Me === null ? Me = u : Me.push.apply(
                  Me,
                  u
                ));
              }
              s = f;
            }
            if (u = !1, s !== 2) continue;
          }
        }
        if (s === 1) {
          _i(t, 0), oa(t, e, 0, !0);
          break;
        }
        t: {
          switch (a = t, u = s, u) {
            case 0:
            case 1:
              throw Error(o(345));
            case 4:
              if ((e & 4194048) !== e && (e & 62914560) !== e)
                break;
            case 6:
              oa(
                a,
                e,
                je,
                !la
              );
              break t;
            case 2:
              Me = null;
              break;
            case 3:
            case 5:
              break;
            default:
              throw Error(o(329));
          }
          if ((e & 62914560) === e && (s = pu + 300 - Ce(), 10 < s)) {
            if (oa(
              a,
              e,
              je,
              !la
            ), ys(a, 0, !0) !== 0) break t;
            vn = e, a.timeoutHandle = Rc(
              Ry.bind(
                null,
                a,
                n,
                Me,
                vu,
                oc,
                e,
                je,
                Ga,
                Ci,
                la,
                u,
                "Throttled",
                -0,
                0
              ),
              s
            );
            break t;
          }
          Ry(
            a,
            n,
            Me,
            vu,
            oc,
            e,
            je,
            Ga,
            Ci,
            la,
            u,
            null,
            -0,
            0
          );
        }
      }
      break;
    } while (!0);
    bn(t);
  }
  function Ry(t, e, n, a, s, u, f, m, S, D, N, w, A, O) {
    t.timeoutHandle = -1;
    var X = e.subtreeFlags, P = (u & 335544064) === u;
    if (w = null, (P || X & 8192 || (X & 16785408) === 16785408) && (w = {
      stylesheets: null,
      count: 0,
      imgCount: 0,
      imgBytes: 0,
      suspenseyImages: [],
      waitingForImages: !0,
      waitingForViewTransition: !1,
      unsuspend: rn
    }, we = null, Ey(
      e,
      u,
      w
    ), P && (X = w, P = t.containerInfo, P = (P.nodeType === 9 ? P : P.ownerDocument).__reactViewTransition, P != null && (X.count++, X.waitingForViewTransition = !0, X = Gl.bind(X), P.finished.then(X, X))), X = (u & 62914560) === u ? pu - Ce() : (u & 4194048) === u ? Cy - Ce() : 0, X = ZS(
      w,
      X
    ), X !== null)) {
      vn = u, t.cancelPendingCommit = X(
        Ly.bind(
          null,
          t,
          e,
          u,
          n,
          a,
          s,
          f,
          m,
          S,
          D,
          N,
          w,
          null,
          A,
          O
        )
      ), oa(t, u, f, !D);
      return;
    }
    Ly(
      t,
      e,
      u,
      n,
      a,
      s,
      f,
      m,
      S,
      D,
      N,
      w
    );
  }
  function qb(t) {
    for (var e = t; ; ) {
      var n = e.tag;
      if ((n === 0 || n === 11 || n === 15) && e.flags & 16384 && (n = e.updateQueue, n !== null && (n = n.stores, n !== null)))
        for (var a = 0; a < n.length; a++) {
          var s = n[a], u = s.getSnapshot;
          s = s.value;
          try {
            if (!Re(u(), s)) return !1;
          } catch {
            return !1;
          }
        }
      if (n = e.child, e.subtreeFlags & 16384 && n !== null)
        n.return = e, e = n;
      else {
        if (e === t) break;
        for (; e.sibling === null; ) {
          if (e.return === null || e.return === t) return !0;
          e = e.return;
        }
        e.sibling.return = e.return, e = e.sibling;
      }
    }
    return !0;
  }
  function oa(t, e, n, a) {
    e = Dh(t, e), e &= ~yu, e &= ~Ga, t.suspendedLanes |= e, t.pingedLanes &= ~e, a && (t.warmLanes |= e), a = t.expirationTimes;
    for (var s = e; 0 < s; ) {
      var u = 31 - Ne(s), f = 1 << u;
      a[u] = -1, s &= ~f;
    }
    n !== 0 && Oh(t, n, e);
  }
  function Su() {
    return (Et & 6) === 0 ? (jl(0), !1) : !0;
  }
  function fc() {
    if (dt !== null) {
      if (Mt === 0)
        var t = dt.return;
      else
        t = dt, _n = za = null, br(t), vi = null, vl = 0, t = dt;
      for (; t !== null; )
        ty(t.alternate, t), t = t.return;
      dt = null;
    }
  }
  function _i(t, e) {
    var n = t.timeoutHandle;
    return n !== -1 && (t.timeoutHandle = -1, fS(n)), n = t.cancelPendingCommit, n !== null && (t.cancelPendingCommit = null, n()), vn = 0, fc(), _t = t, dt = n = zn(t.current, null), yt = e, Mt = 0, Ve = null, la = !1, Di = tl(t, e), uc = !1, Ci = je = yu = Ga = sa = qt = 0, Me = wl = null, oc = !1, Hn = Dh(t, e), Os(), n;
  }
  function _y(t, e) {
    ut = null, W.H = $s, e === gi || e === Ls ? (e = Ld(), Mt = 3) : e === sr ? (e = Ld(), Mt = 4) : Mt = e === Vr ? 8 : e !== null && typeof e == "object" && typeof e.then == "function" ? 6 : 1, Ve = e, dt === null && (qt = 1, tu(
      t,
      qe(e, t.current)
    ));
  }
  function wy() {
    var t = se.current;
    return t === null ? !0 : (yt & 4194048) === yt ? me === null : (yt & 62914560) === yt || (yt & 536870912) !== 0 ? t === me : !1;
  }
  function Vy() {
    var t = W.H;
    return W.H = $s, t === null ? $s : t;
  }
  function jy() {
    var t = W.A;
    return W.A = Lb, t;
  }
  function Tu() {
    qt = 4, la || (yt & 4194048) !== yt && se.current !== null || (Di = !0), (sa & 134217727) === 0 && (Ga & 134217727) === 0 || _t === null || oa(
      _t,
      yt,
      je,
      !1
    );
  }
  function hc(t, e, n) {
    var a = Et;
    Et |= 2;
    var s = Vy(), u = jy();
    (_t !== t || yt !== e) && (vu = null, _i(t, e)), e = !1;
    var f = qt;
    t: do
      try {
        if (Mt !== 0 && dt !== null) {
          var m = dt, S = Ve;
          switch (Mt) {
            case 8:
              fc(), f = 6;
              break t;
            case 3:
            case 2:
            case 9:
            case 6:
              se.current === null && (e = !0);
              var D = Mt;
              if (Mt = 0, Ve = null, wi(t, m, S, D), n && Di) {
                f = 0;
                break t;
              }
              break;
            default:
              D = Mt, Mt = 0, Ve = null, wi(t, m, S, D);
          }
        }
        Gb(), f = qt;
        break;
      } catch (N) {
        _y(t, N);
      }
    while (!0);
    return e && t.shellSuspendCounter++, _n = za = null, Et = a, W.H = s, W.A = u, dt === null && (_t = null, yt = 0, Os()), f;
  }
  function Gb() {
    for (; dt !== null; ) Uy(dt);
  }
  function Xb(t, e) {
    var n = Et;
    Et |= 2;
    var a = Vy(), s = jy();
    _t !== t || yt !== e ? (vu = null, gu = Ce() + 500, _i(t, e)) : Di = tl(
      t,
      e
    );
    t: do
      try {
        if (Mt !== 0 && dt !== null) {
          e = dt;
          var u = Ve;
          e: switch (Mt) {
            case 1:
              Mt = 0, Ve = null, wi(t, e, u, 1);
              break;
            case 2:
            case 9:
              if (Bd(u)) {
                Mt = 0, Ve = null, By(e);
                break;
              }
              e = function() {
                Mt !== 2 && Mt !== 9 || _t !== t || (Mt = 7), bn(t);
              }, u.then(e, e);
              break t;
            case 3:
              Mt = 7;
              break t;
            case 4:
              Mt = 5;
              break t;
            case 7:
              Bd(u) ? (Mt = 0, Ve = null, By(e)) : (Mt = 0, Ve = null, wi(t, e, u, 7));
              break;
            case 5:
              var f = null;
              switch (dt.tag) {
                case 26:
                  f = dt.memoizedState;
                case 5:
                case 27:
                  var m = dt;
                  if (f ? Op(f) : m.stateNode.complete) {
                    Mt = 0, Ve = null;
                    var S = m.sibling;
                    if (S !== null) dt = S;
                    else {
                      var D = m.return;
                      D !== null ? (dt = D, xu(D)) : dt = null;
                    }
                    break e;
                  }
              }
              Mt = 0, Ve = null, wi(t, e, u, 5);
              break;
            case 6:
              Mt = 0, Ve = null, wi(t, e, u, 6);
              break;
            case 8:
              fc(), qt = 6;
              break t;
            default:
              throw Error(o(462));
          }
        }
        Qb();
        break;
      } catch (N) {
        _y(t, N);
      }
    while (!0);
    return _n = za = null, W.H = a, W.A = s, Et = n, dt !== null ? 0 : (_t = null, yt = 0, Os(), qt);
  }
  function Qb() {
    for (; dt !== null && !u1(); )
      Uy(dt);
  }
  function Uy(t) {
    var e = Im(t.alternate, t, Hn);
    t.memoizedProps = t.pendingProps, e === null ? xu(t) : dt = e;
  }
  function By(t) {
    var e = t, n = e.alternate;
    switch (e.tag) {
      case 15:
      case 0:
        e = Zm(
          n,
          e,
          e.pendingProps,
          e.type,
          void 0,
          yt
        );
        break;
      case 11:
        e = Zm(
          n,
          e,
          e.pendingProps,
          e.type.render,
          e.ref,
          yt
        );
        break;
      case 5:
        br(e);
        var a = e;
        a === te && (ft ? (Vs(a), a.tag === 5 && a.stateNode != null && (Ut = a.stateNode)) : (Vs(a), ft = !0));
      default:
        ty(n, e), e = dt = Dd(e, Hn), e = Im(n, e, Hn);
    }
    t.memoizedProps = t.pendingProps, e === null ? xu(t) : dt = e;
  }
  function wi(t, e, n, a) {
    _n = za = null, br(e), vi = null, vl = 0;
    var s = e.return;
    try {
      if (Rb(
        t,
        s,
        e,
        n,
        yt
      )) {
        qt = 1, tu(
          t,
          qe(n, t.current)
        ), dt = null;
        return;
      }
    } catch (u) {
      if (s !== null) throw dt = s, u;
      qt = 1, tu(
        t,
        qe(n, t.current)
      ), dt = null;
      return;
    }
    e.flags & 32768 ? (ft || a === 1 ? t = !0 : Di || (yt & 536870912) !== 0 ? t = !1 : (la = t = !0, (a === 2 || a === 9 || a === 3 || a === 6) && (a = se.current, a !== null && a.tag === 13 && (a.flags |= 16384))), Hy(e, t)) : xu(e);
  }
  function xu(t) {
    var e = t;
    do {
      if ((e.flags & 32768) !== 0) {
        Hy(
          e,
          la
        );
        return;
      }
      t = e.return;
      var n = jb(
        e.alternate,
        e,
        Hn
      );
      if (n !== null) {
        dt = n;
        return;
      }
      if (e = e.sibling, e !== null) {
        dt = e;
        return;
      }
      dt = e = t;
    } while (e !== null);
    qt === 0 && (qt = 5);
  }
  function Hy(t, e) {
    do {
      var n = Ub(t.alternate, t);
      if (n !== null) {
        n.flags &= 32767, dt = n;
        return;
      }
      if (n = t.return, n !== null && (n.flags |= 32768, n.subtreeFlags = 0, n.deletions = null), !e && (t = t.sibling, t !== null)) {
        dt = t;
        return;
      }
      dt = t = n;
    } while (t !== null);
    qt = 6, dt = null;
  }
  function Ly(t, e, n, a, s, u, f, m, S, D, N, w) {
    t.cancelPendingCommit = null;
    do
      Eu();
    while (Lt !== 0);
    if ((Et & 6) !== 0) throw Error(o(327));
    if (e !== null) {
      if (e === t.current) throw Error(o(177));
      t === _t && (dt = _t = null, yt = 0), Xa = e, en = t, vn = n, cc = s, Oy = a, Zb(
        t,
        e,
        n,
        f,
        m,
        S,
        w
      );
    }
  }
  function Zb(t, e, n, a, s, u, f) {
    var m = e.lanes | e.childLanes;
    if (rc = m, m |= Jo, g1(
      t,
      n,
      m,
      a,
      s,
      u
    ), Ni = null, (n & 335544064) === n ? (zi = bb(t), a = 10262) : (zi = null, a = 10256), (e.subtreeFlags & a) !== 0 || (e.flags & a) !== 0 ? (t.callbackNode = null, t.callbackPriority = 0, Wb(fs, function() {
      return pc(), null;
    })) : (t.callbackNode = null, t.callbackPriority = 0), ou = !1, a = (e.flags & 13878) !== 0, (e.subtreeFlags & 13878) !== 0 || a) {
      a = W.T, W.T = null, s = lt.p, lt.p = 2, u = Et, Et |= 4;
      try {
        Bb(t, e, n);
      } finally {
        Et = u, lt.p = s, W.T = a;
      }
    }
    Lt = 1, ou ? Oi = gS(
      f,
      t.containerInfo,
      zi,
      dc,
      mc,
      Jb,
      yc,
      pc,
      Kb
    ) : (dc(), mc(), yc());
  }
  function Kb(t) {
    if (Lt !== 0) {
      var e = en.onRecoverableError;
      e(t, { componentStack: null });
    }
  }
  function Jb() {
    Lt === 3 && (Lt = 0, Ty(Xa, en), Lt = 4);
  }
  function dc() {
    if (Lt === 1) {
      Lt = 0;
      var t = en, e = Xa, n = vn, a = (e.flags & 13878) !== 0;
      if ((e.subtreeFlags & 13878) !== 0 || a) {
        a = W.T, W.T = null;
        var s = lt.p;
        lt.p = 2;
        var u = Et;
        Et |= 4;
        try {
          zl = fu = !1, by(e, t, n), n = Oc;
          var f = pd(t.containerInfo), m = n.focusedElem, S = n.selectionRange;
          if (f !== m && m && m.ownerDocument && yd(
            m.ownerDocument.documentElement,
            m
          )) {
            if (S !== null && Go(m)) {
              var D = S.start, N = S.end;
              if (N === void 0 && (N = D), "selectionStart" in m)
                m.selectionStart = D, m.selectionEnd = Math.min(
                  N,
                  m.value.length
                );
              else {
                var w = m.ownerDocument || document, A = w && w.defaultView || window;
                if (A.getSelection) {
                  var O = A.getSelection(), X = m.textContent.length, P = Math.min(S.start, X), ot = S.end === void 0 ? P : Math.min(S.end, X);
                  !O.extend && P > ot && (f = ot, ot = P, P = f);
                  var M = md(
                    m,
                    P
                  ), x = md(
                    m,
                    ot
                  );
                  if (M && x && (O.rangeCount !== 1 || O.anchorNode !== M.node || O.anchorOffset !== M.offset || O.focusNode !== x.node || O.focusOffset !== x.offset)) {
                    var C = w.createRange();
                    C.setStart(M.node, M.offset), O.removeAllRanges(), P > ot ? (O.addRange(C), O.extend(x.node, x.offset)) : (C.setEnd(x.node, x.offset), O.addRange(C));
                  }
                }
              }
            }
            for (w = [], O = m; O = O.parentNode; )
              O.nodeType === 1 && w.push({
                element: O,
                left: O.scrollLeft,
                top: O.scrollTop
              });
            for (typeof m.focus == "function" && m.focus(), m = 0; m < w.length; m++) {
              var _ = w[m];
              _.element.scrollLeft = _.left, _.element.scrollTop = _.top;
            }
          }
          qi = !!Cc, Oc = Cc = null;
        } finally {
          Et = u, lt.p = s, W.T = a;
        }
      }
      t.current = e, Lt = 2;
    }
  }
  function mc() {
    if (Lt === 2) {
      Lt = 0;
      var t = en, e = Xa, n = (e.flags & 8772) !== 0;
      if ((e.subtreeFlags & 8772) !== 0 || n) {
        n = W.T, W.T = null;
        var a = lt.p;
        lt.p = 2;
        var s = Et;
        Et |= 4;
        try {
          dy(t, e.alternate, e);
        } finally {
          Et = s, lt.p = a, W.T = n;
        }
      }
      Lt = 3;
    }
  }
  function yc() {
    if (Lt === 4 || Lt === 3) {
      Lt = 0;
      var t = Oi;
      Oi = null, o1();
      var e = en, n = Xa, a = vn, s = Oy, u = (a & 335544064) === a ? 10262 : 10256;
      if ((n.subtreeFlags & u) !== 0 || (n.flags & u) !== 0 ? Lt = 5 : (Lt = 0, Xa = en = null, Yy(e, e.pendingLanes)), u = e.pendingLanes, u === 0 && (ua = null), Ao(a), n = n.stateNode, Oe && typeof Oe.onCommitFiberRoot == "function")
        try {
          Oe.onCommitFiberRoot(
            $i,
            n,
            void 0,
            (n.current.flags & 128) === 128
          );
        } catch {
        }
      if (s !== null) {
        n = W.T, u = lt.p, lt.p = 2, W.T = null;
        try {
          for (var f = e.onRecoverableError, m = 0; m < s.length; m++) {
            var S = s[m];
            f(S.value, {
              componentStack: S.stack
            });
          }
        } finally {
          W.T = n, lt.p = u;
        }
      }
      if (s = Ni, f = zi, zi = null, s !== null && (Ni = null, f === null && (f = []), t !== null))
        for (S = 0; S < s.length; S++)
          n = (0, s[S])(
            f
          ), n !== void 0 && t.finished.finally(n);
      (vn & 3) !== 0 && Eu(), bn(e), u = e.pendingLanes, (a & 261930) !== 0 && (u & 42) !== 0 ? e === bu ? Vl++ : (Vl = 0, bu = e) : (Vl = 0, bu = null), jl(0);
    }
  }
  function Yy(t, e) {
    (t.pooledCacheLanes &= e) === 0 && (e = t.pooledCache, e != null && (t.pooledCache = null, yl(e)));
  }
  function Eu() {
    return Oi !== null && (Oi.skipTransition(), Oi = null), dc(), mc(), yc(), pc();
  }
  function pc() {
    if (Lt !== 5) return !1;
    var t = en, e = rc;
    rc = 0;
    var n = Ao(vn), a = W.T, s = lt.p;
    try {
      lt.p = 32 > n ? 32 : n, W.T = null, n = cc, cc = null;
      var u = en, f = vn;
      if (Lt = 0, Xa = en = null, vn = 0, (Et & 6) !== 0) throw Error(o(331));
      var m = Et;
      if (Et |= 4, My(u.current), xy(
        u,
        u.current,
        f,
        n
      ), Et = m, jl(0, !1), Oe && typeof Oe.onPostCommitFiberRoot == "function")
        try {
          Oe.onPostCommitFiberRoot($i, u);
        } catch {
        }
      return !0;
    } finally {
      lt.p = s, W.T = a, Yy(t, e);
    }
  }
  function qy(t, e, n) {
    e = qe(n, e), e = wr(t.stateNode, e, 2), t = $n(t, e, 2), t !== null && (el(t, 2), bn(t));
  }
  function Dt(t, e, n) {
    if (t.tag === 3)
      qy(t, t, n);
    else
      for (; e !== null; ) {
        if (e.tag === 3) {
          qy(
            e,
            t,
            n
          );
          break;
        } else if (e.tag === 1) {
          var a = e.stateNode;
          if (typeof e.type.getDerivedStateFromError == "function" || typeof a.componentDidCatch == "function" && (ua === null || !ua.has(a))) {
            t = qe(n, t), n = Bm(2), a = $n(e, n, 2), a !== null && (Hm(
              n,
              a,
              e,
              t
            ), el(a, 2), bn(a));
            break;
          }
        }
        e = e.return;
      }
  }
  function gc(t, e, n) {
    var a = t.pingCache;
    if (a === null) {
      a = t.pingCache = new Yb();
      var s = /* @__PURE__ */ new Set();
      a.set(e, s);
    } else
      s = a.get(e), s === void 0 && (s = /* @__PURE__ */ new Set(), a.set(e, s));
    s.has(n) || (uc = !0, s.add(n), t = kb.bind(null, t, e, n), e.then(t, t));
  }
  function kb(t, e, n) {
    var a = t.pingCache;
    a !== null && a.delete(e), t.pingedLanes |= t.suspendedLanes & n, t.warmLanes &= ~n, _t === t && (yt & n) === n && ((qt === 4 || qt === 3 && (yt & 62914560) === yt && 300 > Ce() - pu) && (Et & 2) === 0 ? _i(t, 0) : yu |= n, Ci === yt && (Ci = 0)), bn(t);
  }
  function Gy(t, e) {
    e === 0 && (e = Ch()), t = Ca(t, e), t !== null && (el(t, e), bn(t));
  }
  function Pb(t) {
    var e = t.memoizedState, n = 0;
    e !== null && (n = e.retryLane), Gy(t, n);
  }
  function Fb(t, e) {
    var n = 0;
    switch (t.tag) {
      case 31:
      case 13:
        var a = t.stateNode, s = t.memoizedState;
        s !== null && (n = s.retryLane);
        break;
      case 19:
        a = t.stateNode;
        break;
      case 22:
        a = t.stateNode._retryCache;
        break;
      default:
        throw Error(o(314));
    }
    a !== null && a.delete(e), Gy(t, n);
  }
  function Wb(t, e) {
    return So(t, e);
  }
  var Vi = null, ji = null, vc = !1, Au = !1, bc = !1, ra = 0;
  function bn(t) {
    t !== ji && t.next === null && (ji === null ? Vi = ji = t : ji = ji.next = t), Au = !0, vc || (vc = !0, $b());
  }
  function jl(t, e) {
    if (!bc && Au) {
      bc = !0;
      do
        for (var n = !1, a = Vi; a !== null; ) {
          if (t !== 0) {
            var s = a.pendingLanes;
            if (s === 0) var u = 0;
            else {
              var f = a.suspendedLanes, m = a.pingedLanes;
              u = (1 << 31 - Ne(42 | t) + 1) - 1, u &= s & ~(f & ~m), u = u & 201326741 ? u & 201326741 | 1 : u ? u | 2 : 0;
            }
            u !== 0 && (n = !0, Ky(a, u));
          } else
            u = yt, u = ys(
              a,
              a === _t ? u : 0,
              a.cancelPendingCommit !== null || a.timeoutHandle !== -1
            ), (u & 3) === 0 || tl(a, u) || (n = !0, Ky(a, u));
          a = a.next;
        }
      while (n);
      bc = !1;
    }
  }
  function Ib() {
    Xy();
  }
  function Xy() {
    Au = vc = !1;
    var t = 0;
    ra !== 0 && cS() && (t = ra);
    for (var e = Ce(), n = null, a = Vi; a !== null; ) {
      var s = a.next, u = Qy(a, e);
      u === 0 ? (a.next = null, n === null ? Vi = s : n.next = s, s === null && (ji = n)) : (n = a, (t !== 0 || (u & 3) !== 0) && (Au = !0)), a = s;
    }
    Lt !== 0 && Lt !== 5 || jl(t), ra !== 0 && (ra = 0);
  }
  function Qy(t, e) {
    for (var n = t.suspendedLanes, a = t.pingedLanes, s = t.expirationTimes, u = t.pendingLanes & -62914561; 0 < u; ) {
      var f = 31 - Ne(u), m = 1 << f, S = s[f];
      S === -1 ? ((m & n) === 0 || (m & a) !== 0) && (s[f] = p1(m, e)) : S <= e && (t.expiredLanes |= m), u &= ~m;
    }
    if (e = _t, n = yt, n = ys(
      t,
      t === e ? n : 0,
      t.cancelPendingCommit !== null || t.timeoutHandle !== -1
    ), a = t.callbackNode, n === 0 || t === e && (Mt === 2 || Mt === 9) || t.cancelPendingCommit !== null)
      return a !== null && a !== null && To(a), t.callbackNode = null, t.callbackPriority = 0;
    if ((n & 3) === 0 || tl(t, n)) {
      if (e = n & -n, e === t.callbackPriority) return e;
      switch (a !== null && To(a), Ao(n)) {
        case 2:
        case 8:
          n = Ah;
          break;
        case 32:
          n = fs;
          break;
        case 268435456:
          n = Mh;
          break;
        default:
          n = fs;
      }
      return a = Zy.bind(null, t), n = So(n, a), t.callbackPriority = e, t.callbackNode = n, e;
    }
    return a !== null && a !== null && To(a), t.callbackPriority = 2, t.callbackNode = null, 2;
  }
  function Zy(t, e) {
    if (Lt !== 0 && Lt !== 5)
      return t.callbackNode = null, t.callbackPriority = 0, null;
    var n = t.callbackNode;
    if (Eu() && t.callbackNode !== n)
      return null;
    var a = yt;
    return a = ys(
      t,
      t === _t ? a : 0,
      t.cancelPendingCommit !== null || t.timeoutHandle !== -1
    ), a === 0 ? null : (zy(t, a, e), Qy(t, Ce()), t.callbackNode != null && t.callbackNode === n ? Zy.bind(null, t) : null);
  }
  function Ky(t, e) {
    if (Eu()) return null;
    zy(t, e, !0);
  }
  function $b() {
    hS(function() {
      (Et & 6) !== 0 ? So(
        Eh,
        Ib
      ) : Xy();
    });
  }
  function Sc() {
    if (ra === 0) {
      var t = wa;
      t === 0 && (t = hs, hs <<= 1, (hs & 261888) === 0 && (hs = 256)), ra = t;
    }
    return ra;
  }
  function Jy(t) {
    return t == null || typeof t == "symbol" || typeof t == "boolean" ? null : typeof t == "function" ? t : Ss(t);
  }
  function tS(t, e, n, a, s) {
    if (e === "submit" && n && n.stateNode === s) {
      var u = Jy(
        (s[Te] || null).action
      ), f = a.submitter;
      f && (e = (e = f[Te] || null) ? Jy(e.formAction) : f.getAttribute("formAction"), e !== null && (u = e, f = null));
      var m = new As(
        "action",
        "action",
        null,
        a,
        s
      );
      t.push({
        event: m,
        listeners: [
          {
            instance: null,
            listener: function() {
              if (a.defaultPrevented) {
                if (ra !== 0) {
                  var S = new FormData(s, f);
                  Or(
                    n,
                    {
                      pending: !0,
                      data: S,
                      method: s.method,
                      action: u
                    },
                    null,
                    S
                  );
                }
              } else
                typeof u == "function" && (m.preventDefault(), S = new FormData(s, f), Or(
                  n,
                  {
                    pending: !0,
                    data: S,
                    method: s.method,
                    action: u
                  },
                  u,
                  S
                ));
            },
            currentTarget: s
          }
        ]
      });
    }
  }
  for (var Tc = 0; Tc < Ko.length; Tc++) {
    var xc = Ko[Tc], eS = xc.toLowerCase(), nS = xc[0].toUpperCase() + xc.slice(1);
    We(
      eS,
      "on" + nS
    );
  }
  We(bd, "onAnimationEnd"), We(Sd, "onAnimationIteration"), We(Td, "onAnimationStart"), We("dblclick", "onDoubleClick"), We("focusin", "onFocus"), We("focusout", "onBlur"), We(fb, "onTransitionRun"), We(hb, "onTransitionStart"), We(db, "onTransitionCancel"), We(xd, "onTransitionEnd"), ai("onMouseEnter", ["mouseout", "mouseover"]), ai("onMouseLeave", ["mouseout", "mouseover"]), ai("onPointerEnter", ["pointerout", "pointerover"]), ai("onPointerLeave", ["pointerout", "pointerover"]), Aa(
    "onChange",
    "change click focusin focusout input keydown keyup selectionchange".split(" ")
  ), Aa(
    "onSelect",
    "focusout contextmenu dragend focusin keydown keyup mousedown mouseup selectionchange".split(
      " "
    )
  ), Aa("onBeforeInput", [
    "compositionend",
    "keypress",
    "textInput",
    "paste"
  ]), Aa(
    "onCompositionEnd",
    "compositionend focusout keydown keypress keyup mousedown".split(" ")
  ), Aa(
    "onCompositionStart",
    "compositionstart focusout keydown keypress keyup mousedown".split(" ")
  ), Aa(
    "onCompositionUpdate",
    "compositionupdate focusout keydown keypress keyup mousedown".split(" ")
  );
  var Ul = "abort canplay canplaythrough durationchange emptied encrypted ended error loadeddata loadedmetadata loadstart pause play playing progress ratechange resize seeked seeking stalled suspend timeupdate volumechange waiting".split(
    " "
  ), aS = new Set(
    "beforetoggle cancel close invalid load scroll scrollend toggle".split(" ").concat(Ul)
  );
  function ky(t, e) {
    e = (e & 4) !== 0;
    for (var n = 0; n < t.length; n++) {
      var a = t[n], s = a.event;
      a = a.listeners;
      t: {
        var u = void 0;
        if (e)
          for (var f = a.length - 1; 0 <= f; f--) {
            var m = a[f], S = m.instance, D = m.currentTarget;
            if (m = m.listener, S !== u && s.isPropagationStopped())
              break t;
            u = m, s.currentTarget = D;
            try {
              u(s);
            } catch (N) {
              Cs(N);
            }
            s.currentTarget = null, u = S;
          }
        else
          for (f = 0; f < a.length; f++) {
            if (m = a[f], S = m.instance, D = m.currentTarget, m = m.listener, S !== u && s.isPropagationStopped())
              break t;
            u = m, s.currentTarget = D;
            try {
              u(s);
            } catch (N) {
              Cs(N);
            }
            s.currentTarget = null, u = S;
          }
      }
    }
  }
  function mt(t, e) {
    var n = e[wh];
    n === void 0 && (n = e[wh] = /* @__PURE__ */ new Set());
    var a = t + "__bubble";
    n.has(a) || (Py(e, t, 2, !1), n.add(a));
  }
  function Ec(t, e, n) {
    var a = 0;
    e && (a |= 4), Py(
      n,
      t,
      a,
      e
    );
  }
  var Mu = "_reactListening" + Math.random().toString(36).slice(2);
  function Ac(t) {
    if (!t[Mu]) {
      t[Mu] = !0, Uh.forEach(function(n) {
        n !== "selectionchange" && (aS.has(n) || Ec(n, !1, t), Ec(n, !0, t));
      });
      var e = t.nodeType === 9 ? t : t.ownerDocument;
      e === null || e[Mu] || (e[Mu] = !0, Ec("selectionchange", !1, e));
    }
  }
  function Py(t, e, n, a) {
    switch (Hp(e)) {
      case 2:
        var s = PS;
        break;
      case 8:
        s = FS;
        break;
      default:
        s = Qc;
    }
    n = s.bind(
      null,
      e,
      n,
      t
    ), s = void 0, !_o || e !== "touchstart" && e !== "touchmove" && e !== "wheel" || (s = !0), a ? s !== void 0 ? t.addEventListener(e, n, {
      capture: !0,
      passive: s
    }) : t.addEventListener(e, n, !0) : s !== void 0 ? t.addEventListener(e, n, {
      passive: s
    }) : t.addEventListener(e, n, !1);
  }
  function Mc(t, e, n, a, s) {
    var u = a;
    if ((e & 1) === 0 && (e & 2) === 0 && a !== null)
      t: for (; ; ) {
        if (a === null) return;
        var f = a.tag;
        if (f === 3 || f === 4) {
          var m = a.stateNode.containerInfo;
          if (m === s) break;
          if (f === 4)
            for (f = a.return; f !== null; ) {
              var S = f.tag;
              if ((S === 3 || S === 4) && f.stateNode.containerInfo === s)
                return;
              f = f.return;
            }
          for (; m !== null; ) {
            if (f = Ea(m), f === null) return;
            if (S = f.tag, S === 5 || S === 6 || S === 26 || S === 27) {
              a = u = f;
              continue t;
            }
            m = m.parentNode;
          }
        }
        a = a.return;
      }
    Ph(function() {
      var D = u, N = zo(n), w = [];
      t: {
        var A = Ed.get(t);
        if (A !== void 0) {
          var O = As, X = t;
          switch (t) {
            case "keypress":
              if (xs(n) === 0) break t;
            case "keydown":
            case "keyup":
              O = q1;
              break;
            case "focusin":
              X = "focus", O = Uo;
              break;
            case "focusout":
              X = "blur", O = Uo;
              break;
            case "beforeblur":
            case "afterblur":
              O = Uo;
              break;
            case "click":
              if (n.button === 2) break t;
            case "auxclick":
            case "dblclick":
            case "mousedown":
            case "mousemove":
            case "mouseup":
            case "mouseout":
            case "mouseover":
            case "contextmenu":
              O = Ih;
              break;
            case "drag":
            case "dragend":
            case "dragenter":
            case "dragexit":
            case "dragleave":
            case "dragover":
            case "dragstart":
            case "drop":
              O = N1;
              break;
            case "touchcancel":
            case "touchend":
            case "touchmove":
            case "touchstart":
              O = K1;
              break;
            case bd:
            case Sd:
            case Td:
              O = _1;
              break;
            case xd:
              O = k1;
              break;
            case "scroll":
            case "scrollend":
              O = C1;
              break;
            case "wheel":
              O = F1;
              break;
            case "copy":
            case "cut":
            case "paste":
              O = V1;
              break;
            case "gotpointercapture":
            case "lostpointercapture":
            case "pointercancel":
            case "pointerdown":
            case "pointermove":
            case "pointerout":
            case "pointerover":
            case "pointerup":
              O = td;
              break;
            case "submit":
              O = Q1;
              break;
            case "toggle":
            case "beforetoggle":
              O = I1;
          }
          var P = (e & 4) !== 0, ot = !P && (t === "scroll" || t === "scrollend"), M = P ? A !== null ? A + "Capture" : null : A;
          P = [];
          for (var x = D, C; x !== null; ) {
            var _ = x;
            if (C = _.stateNode, _ = _.tag, _ !== 5 && _ !== 26 && _ !== 27 || C === null || M === null || (_ = il(x, M), _ != null && P.push(
              Bl(x, _, C)
            )), ot) break;
            x = x.return;
          }
          0 < P.length && (A = new O(
            A,
            X,
            null,
            n,
            N
          ), w.push({ event: A, listeners: P }));
        }
      }
      if ((e & 7) === 0) {
        t: {
          if (O = t === "mouseover" || t === "pointerover", A = t === "mouseout" || t === "pointerout", O && n !== No && (X = n.relatedTarget || n.fromElement) && (Ea(X) || X[ti]))
            break t;
          (A || O) && (X = N.window === N ? N : (O = N.ownerDocument) ? O.defaultView || O.parentWindow : window, A ? (O = n.relatedTarget || n.toElement, A = D, O = O ? Ea(O) : null, O !== null && (ot = d(O), P = O.tag, O !== ot || P !== 5 && P !== 27 && P !== 6) && (O = null)) : (A = null, O = D), A !== O && (P = Ih, _ = "onMouseLeave", M = "onMouseEnter", x = "mouse", (t === "pointerout" || t === "pointerover") && (P = td, _ = "onPointerLeave", M = "onPointerEnter", x = "pointer"), ot = A == null ? X : al(A), C = O == null ? X : al(O), X = new P(
            _,
            x + "leave",
            A,
            n,
            N
          ), X.target = ot, X.relatedTarget = C, _ = null, Ea(N) === D && (P = new P(
            M,
            x + "enter",
            O,
            n,
            N
          ), P.target = C, P.relatedTarget = ot, _ = P), ot = _, P = A && O ? rt(
            A,
            O,
            iS
          ) : null, A !== null && Fy(
            w,
            X,
            A,
            P,
            !1
          ), O !== null && ot !== null && Fy(
            w,
            ot,
            O,
            P,
            !0
          )));
        }
        t: {
          if (A = D ? al(D) : window, O = A.nodeName && A.nodeName.toLowerCase(), O === "select" || O === "input" && A.type === "file")
            var Z = od;
          else if (sd(A))
            if (rd)
              Z = ob;
            else {
              Z = sb;
              var pt = lb;
            }
          else
            O = A.nodeName, !O || O.toLowerCase() !== "input" || A.type !== "checkbox" && A.type !== "radio" ? D && Oo(D.elementType) && (Z = od) : Z = ub;
          if (Z && (Z = Z(t, D))) {
            ud(
              w,
              Z,
              n,
              N
            );
            break t;
          }
          pt && pt(t, A, D);
        }
        switch (pt = D ? al(D) : window, t) {
          case "focusin":
            (sd(pt) || pt.contentEditable === "true") && (ri = pt, Xo = D, hl = null);
            break;
          case "focusout":
            hl = Xo = ri = null;
            break;
          case "mousedown":
            Qo = !0;
            break;
          case "contextmenu":
          case "mouseup":
          case "dragend":
            Qo = !1, gd(w, n, N);
            break;
          case "selectionchange":
            if (cb) break;
          case "keydown":
          case "keyup":
            gd(w, n, N);
        }
        var I;
        if (Ho)
          t: {
            switch (t) {
              case "compositionstart":
                var at = "onCompositionStart";
                break t;
              case "compositionend":
                at = "onCompositionEnd";
                break t;
              case "compositionupdate":
                at = "onCompositionUpdate";
                break t;
            }
            at = void 0;
          }
        else
          oi ? id(t, n) && (at = "onCompositionEnd") : t === "keydown" && n.keyCode === 229 && (at = "onCompositionStart");
        at && (ed && n.locale !== "ko" && (oi || at !== "onCompositionStart" ? at === "onCompositionEnd" && oi && (I = Fh()) : (Qn = N, wo = "value" in Qn ? Qn.value : Qn.textContent, oi = !0)), pt = Du(D, at), 0 < pt.length && (at = new $h(
          at,
          t,
          null,
          n,
          N
        ), w.push({ event: at, listeners: pt }), I ? at.data = I : (I = ld(n), I !== null && (at.data = I)))), (I = tb ? eb(t, n) : nb(t, n)) && (at = Du(D, "onBeforeInput"), 0 < at.length && (pt = new $h(
          "onBeforeInput",
          "beforeinput",
          null,
          n,
          N
        ), w.push({
          event: pt,
          listeners: at
        }), pt.data = I)), tS(
          w,
          t,
          D,
          n,
          N
        );
      }
      ky(w, e);
    });
  }
  function Bl(t, e, n) {
    return {
      instance: t,
      listener: e,
      currentTarget: n
    };
  }
  function Du(t, e) {
    for (var n = e + "Capture", a = []; t !== null; ) {
      var s = t, u = s.stateNode;
      if (s = s.tag, s !== 5 && s !== 26 && s !== 27 || u === null || (s = il(t, n), s != null && a.unshift(
        Bl(t, s, u)
      ), s = il(t, e), s != null && a.push(
        Bl(t, s, u)
      )), t.tag === 3) return a;
      t = t.return;
    }
    return [];
  }
  function iS(t) {
    if (t === null) return null;
    do
      t = t.return;
    while (t && t.tag !== 5 && t.tag !== 27);
    return t || null;
  }
  function Fy(t, e, n, a, s) {
    for (var u = e._reactName, f = []; n !== null && n !== a; ) {
      var m = n, S = m.alternate, D = m.stateNode;
      if (m = m.tag, S !== null && S === a) break;
      m !== 5 && m !== 26 && m !== 27 || D === null || (S = D, s ? (D = il(n, u), D != null && f.unshift(
        Bl(n, D, S)
      )) : s || (D = il(n, u), D != null && f.push(
        Bl(n, D, S)
      ))), n = n.return;
    }
    f.length !== 0 && t.push({ event: e, listeners: f });
  }
  var lS = /\r\n?/g, sS = /\u0000|\uFFFD/g;
  function Wy(t) {
    return (typeof t == "string" ? t : "" + t).replace(lS, `
`).replace(sS, "");
  }
  function Iy(t, e) {
    return e = Wy(e), Wy(t) === e;
  }
  function Ct(t, e, n, a, s, u) {
    switch (n) {
      case "children":
        if (typeof a == "string")
          e === "body" || e === "textarea" && a === "" || li(t, a);
        else if (typeof a == "number" || typeof a == "bigint")
          e !== "body" && li(t, "" + a);
        else return;
        break;
      case "className":
        bs(t, "class", a);
        break;
      case "tabIndex":
        bs(t, "tabindex", a);
        break;
      case "dir":
      case "role":
      case "viewBox":
      case "width":
      case "height":
        bs(t, n, a);
        break;
      case "style":
        Jh(t, a, u);
        return;
      case "data":
        if (e !== "object") {
          bs(t, "data", a);
          break;
        }
      case "src":
      case "href":
        if (a === "" && (e !== "a" || n !== "href")) {
          t.removeAttribute(n);
          break;
        }
        if (a == null || typeof a == "function" || typeof a == "symbol" || typeof a == "boolean") {
          t.removeAttribute(n);
          break;
        }
        a = Ss(a), t.setAttribute(n, a);
        break;
      case "action":
      case "formAction":
        if (typeof a == "function") {
          t.setAttribute(
            n,
            "javascript:throw new Error('A React form was unexpectedly submitted. If you called form.submit() manually, consider using form.requestSubmit() instead. If you\\'re trying to use event.stopPropagation() in a submit event handler, consider also calling event.preventDefault().')"
          );
          break;
        } else
          typeof u == "function" && (n === "formAction" ? (e !== "input" && Ct(t, e, "name", s.name, s, null), Ct(
            t,
            e,
            "formEncType",
            s.formEncType,
            s,
            null
          ), Ct(
            t,
            e,
            "formMethod",
            s.formMethod,
            s,
            null
          ), Ct(
            t,
            e,
            "formTarget",
            s.formTarget,
            s,
            null
          )) : (Ct(t, e, "encType", s.encType, s, null), Ct(t, e, "method", s.method, s, null), Ct(t, e, "target", s.target, s, null)));
        if (a == null || typeof a == "symbol" || typeof a == "boolean") {
          t.removeAttribute(n);
          break;
        }
        a = Ss(a), t.setAttribute(n, a);
        break;
      case "onClick":
        a != null && (t.onclick = rn);
        return;
      case "onScroll":
        a != null && mt("scroll", t);
        return;
      case "onScrollEnd":
        a != null && mt("scrollend", t);
        return;
      case "dangerouslySetInnerHTML":
        if (a != null) {
          if (typeof a != "object" || !("__html" in a))
            throw Error(o(61));
          if (n = a.__html, n != null) {
            if (s.children != null) throw Error(o(60));
            u?.__html !== n && (t.innerHTML = n);
          }
        }
        break;
      case "multiple":
        t.multiple = a && typeof a != "function" && typeof a != "symbol";
        break;
      case "muted":
        t.muted = a && typeof a != "function" && typeof a != "symbol";
        break;
      case "suppressContentEditableWarning":
      case "suppressHydrationWarning":
      case "defaultValue":
      case "defaultChecked":
      case "innerHTML":
      case "ref":
        break;
      case "autoFocus":
        break;
      case "xlinkHref":
        if (a == null || typeof a == "function" || typeof a == "boolean" || typeof a == "symbol") {
          t.removeAttribute("xlink:href");
          break;
        }
        n = Ss(a), t.setAttributeNS(
          "http://www.w3.org/1999/xlink",
          "xlink:href",
          n
        );
        break;
      case "contentEditable":
      case "spellCheck":
      case "draggable":
      case "value":
      case "autoReverse":
      case "externalResourcesRequired":
      case "focusable":
      case "preserveAlpha":
        a != null && typeof a != "function" && typeof a != "symbol" ? t.setAttribute(n, a) : t.removeAttribute(n);
        break;
      case "inert":
      case "allowFullScreen":
      case "async":
      case "autoPlay":
      case "controls":
      case "credentialless":
      case "default":
      case "defer":
      case "disabled":
      case "disablePictureInPicture":
      case "disableRemotePlayback":
      case "formNoValidate":
      case "hidden":
      case "loop":
      case "noModule":
      case "noValidate":
      case "open":
      case "playsInline":
      case "readOnly":
      case "required":
      case "reversed":
      case "scoped":
      case "seamless":
      case "itemScope":
        a && typeof a != "function" && typeof a != "symbol" ? t.setAttribute(n, "") : t.removeAttribute(n);
        break;
      case "capture":
      case "download":
        a === !0 ? t.setAttribute(n, "") : a !== !1 && a != null && typeof a != "function" && typeof a != "symbol" ? t.setAttribute(n, a) : t.removeAttribute(n);
        break;
      case "cols":
      case "rows":
      case "size":
      case "span":
        a != null && typeof a != "function" && typeof a != "symbol" && !isNaN(a) && 1 <= a ? t.setAttribute(n, a) : t.removeAttribute(n);
        break;
      case "rowSpan":
      case "start":
        a == null || typeof a == "function" || typeof a == "symbol" || isNaN(a) ? t.removeAttribute(n) : t.setAttribute(n, a);
        break;
      case "popover":
        mt("beforetoggle", t), mt("toggle", t), vs(t, "popover", a);
        break;
      case "xlinkActuate":
        Dn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:actuate",
          a
        );
        break;
      case "xlinkArcrole":
        Dn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:arcrole",
          a
        );
        break;
      case "xlinkRole":
        Dn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:role",
          a
        );
        break;
      case "xlinkShow":
        Dn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:show",
          a
        );
        break;
      case "xlinkTitle":
        Dn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:title",
          a
        );
        break;
      case "xlinkType":
        Dn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:type",
          a
        );
        break;
      case "xmlBase":
        Dn(
          t,
          "http://www.w3.org/XML/1998/namespace",
          "xml:base",
          a
        );
        break;
      case "xmlLang":
        Dn(
          t,
          "http://www.w3.org/XML/1998/namespace",
          "xml:lang",
          a
        );
        break;
      case "xmlSpace":
        Dn(
          t,
          "http://www.w3.org/XML/1998/namespace",
          "xml:space",
          a
        );
        break;
      case "is":
        vs(t, "is", a);
        break;
      case "innerText":
      case "textContent":
        return;
      default:
        if (!(2 < n.length) || n[0] !== "o" && n[0] !== "O" || n[1] !== "n" && n[1] !== "N")
          n = M1.get(n) || n, vs(t, n, a);
        else return;
    }
    Tt = !0;
  }
  function Dc(t, e, n, a, s, u) {
    switch (n) {
      case "style":
        Jh(t, a, u);
        return;
      case "dangerouslySetInnerHTML":
        if (a != null) {
          if (typeof a != "object" || !("__html" in a))
            throw Error(o(61));
          if (n = a.__html, n != null) {
            if (s.children != null) throw Error(o(60));
            u?.__html !== n && (t.innerHTML = n);
          }
        }
        break;
      case "children":
        if (typeof a == "string") li(t, a);
        else if (typeof a == "number" || typeof a == "bigint")
          li(t, "" + a);
        else return;
        break;
      case "onScroll":
        a != null && mt("scroll", t);
        return;
      case "onScrollEnd":
        a != null && mt("scrollend", t);
        return;
      case "onClick":
        a != null && (t.onclick = rn);
        return;
      case "suppressContentEditableWarning":
      case "suppressHydrationWarning":
      case "innerHTML":
      case "ref":
        return;
      case "innerText":
      case "textContent":
        return;
      default:
        if (!Bh.hasOwnProperty(n))
          t: {
            if (n[0] === "o" && n[1] === "n" && (s = n.endsWith("Capture"), u = n.slice(2, s ? n.length - 7 : void 0), e = t[Te] || null, e = e != null ? e[n] : null, typeof e == "function" && t.removeEventListener(u, e, s), typeof a == "function")) {
              typeof e != "function" && e !== null && (n in t ? t[n] = null : t.hasAttribute(n) && t.removeAttribute(n)), t.addEventListener(u, a, s);
              break t;
            }
            Tt = !0, n in t ? t[n] = a : a === !0 ? t.setAttribute(n, "") : vs(t, n, a);
          }
        return;
    }
    Tt = !0;
  }
  function re(t, e, n) {
    switch (e) {
      case "div":
      case "span":
      case "svg":
      case "path":
      case "a":
      case "g":
      case "p":
      case "li":
        break;
      case "img":
        mt("error", t), mt("load", t);
        var a = !1, s = !1, u;
        for (u in n)
          if (n.hasOwnProperty(u)) {
            var f = n[u];
            if (f != null)
              switch (u) {
                case "src":
                  a = !0;
                  break;
                case "srcSet":
                  s = !0;
                  break;
                case "children":
                case "dangerouslySetInnerHTML":
                  throw Error(o(137, e));
                default:
                  Ct(t, e, u, f, n, null);
              }
          }
        s && Ct(t, e, "srcSet", n.srcSet, n, null), a && Ct(t, e, "src", n.src, n, null);
        return;
      case "input":
        mt("invalid", t);
        var m = u = f = s = null, S = null, D = null;
        for (a in n)
          if (n.hasOwnProperty(a)) {
            var N = n[a];
            if (N != null)
              switch (a) {
                case "name":
                  s = N;
                  break;
                case "type":
                  f = N;
                  break;
                case "checked":
                  S = N;
                  break;
                case "defaultChecked":
                  D = N;
                  break;
                case "value":
                  u = N;
                  break;
                case "defaultValue":
                  m = N;
                  break;
                case "children":
                case "dangerouslySetInnerHTML":
                  if (N != null)
                    throw Error(o(137, e));
                  break;
                default:
                  Ct(t, e, a, N, n, null);
              }
          }
        Xh(
          t,
          u,
          m,
          S,
          D,
          f,
          s,
          !1
        );
        return;
      case "select":
        mt("invalid", t), a = f = u = null;
        for (s in n)
          if (n.hasOwnProperty(s) && (m = n[s], m != null))
            switch (s) {
              case "value":
                u = m;
                break;
              case "defaultValue":
                f = m;
                break;
              case "multiple":
                a = m;
              default:
                Ct(t, e, s, m, n, null);
            }
        e = u, n = f, t.multiple = !!a, e != null ? ii(t, !!a, e, !1) : n != null && ii(t, !!a, n, !0);
        return;
      case "textarea":
        mt("invalid", t), u = s = a = null;
        for (f in n)
          if (n.hasOwnProperty(f) && (m = n[f], m != null))
            switch (f) {
              case "value":
                a = m;
                break;
              case "defaultValue":
                s = m;
                break;
              case "children":
                u = m;
                break;
              case "dangerouslySetInnerHTML":
                if (m != null) throw Error(o(91));
                break;
              default:
                Ct(t, e, f, m, n, null);
            }
        Zh(t, a, s, u);
        return;
      case "option":
        for (S in n)
          n.hasOwnProperty(S) && (a = n[S], a != null) && (S === "selected" ? t.selected = a && typeof a != "function" && typeof a != "symbol" : Ct(t, e, S, a, n, null));
        return;
      case "dialog":
        mt("beforetoggle", t), mt("toggle", t), mt("cancel", t), mt("close", t);
        break;
      case "iframe":
      case "object":
        mt("load", t);
        break;
      case "video":
      case "audio":
        for (a = 0; a < Ul.length; a++)
          mt(Ul[a], t);
        break;
      case "image":
        mt("error", t), mt("load", t);
        break;
      case "details":
        mt("toggle", t);
        break;
      case "embed":
      case "source":
      case "link":
        mt("error", t), mt("load", t);
      case "area":
      case "base":
      case "br":
      case "col":
      case "hr":
      case "keygen":
      case "meta":
      case "param":
      case "track":
      case "wbr":
      case "menuitem":
        for (D in n)
          if (n.hasOwnProperty(D) && (a = n[D], a != null))
            switch (D) {
              case "children":
              case "dangerouslySetInnerHTML":
                throw Error(o(137, e));
              default:
                Ct(t, e, D, a, n, null);
            }
        return;
      default:
        if (Oo(e)) {
          for (N in n)
            n.hasOwnProperty(N) && (a = n[N], a !== void 0 && Dc(
              t,
              e,
              N,
              a,
              n,
              void 0
            ));
          return;
        }
    }
    for (m in n)
      n.hasOwnProperty(m) && (a = n[m], a != null && Ct(t, e, m, a, n, null));
  }
  var uS = {};
  function oS(t, e, n, a) {
    switch (e) {
      case "div":
      case "span":
      case "svg":
      case "path":
      case "a":
      case "g":
      case "p":
      case "li":
        break;
      case "input":
        var s = null, u = null, f = null, m = null, S = null, D = null, N = null;
        for (O in n) {
          var w = n[O];
          if (n.hasOwnProperty(O) && w != null)
            switch (O) {
              case "checked":
                break;
              case "value":
                break;
              case "defaultValue":
                S = w;
              default:
                a.hasOwnProperty(O) || Ct(t, e, O, null, a, w);
            }
        }
        for (var A in a) {
          var O = a[A];
          if (w = n[A], a.hasOwnProperty(A) && (O != null || w != null))
            switch (A) {
              case "type":
                O !== w && (Tt = !0), u = O;
                break;
              case "name":
                O !== w && (Tt = !0), s = O;
                break;
              case "checked":
                O !== w && (Tt = !0), D = O;
                break;
              case "defaultChecked":
                O !== w && (Tt = !0), N = O;
                break;
              case "value":
                O !== w && (Tt = !0), f = O;
                break;
              case "defaultValue":
                O !== w && (Tt = !0), m = O;
                break;
              case "children":
              case "dangerouslySetInnerHTML":
                if (O != null)
                  throw Error(o(137, e));
                break;
              default:
                O !== w && Ct(
                  t,
                  e,
                  A,
                  O,
                  a,
                  w
                );
            }
        }
        Do(
          t,
          f,
          m,
          S,
          D,
          N,
          u,
          s
        );
        return;
      case "select":
        O = f = m = A = null;
        for (u in n)
          if (S = n[u], n.hasOwnProperty(u) && S != null)
            switch (u) {
              case "value":
                break;
              case "multiple":
                O = S;
              default:
                a.hasOwnProperty(u) || Ct(
                  t,
                  e,
                  u,
                  null,
                  a,
                  S
                );
            }
        for (s in a)
          if (u = a[s], S = n[s], a.hasOwnProperty(s) && (u != null || S != null))
            switch (s) {
              case "value":
                u !== S && (Tt = !0), A = u;
                break;
              case "defaultValue":
                u !== S && (Tt = !0), m = u;
                break;
              case "multiple":
                u !== S && (Tt = !0), f = u;
              default:
                u !== S && Ct(
                  t,
                  e,
                  s,
                  u,
                  a,
                  S
                );
            }
        e = m, n = f, a = O, A != null ? ii(t, !!n, A, !1) : !!a != !!n && (e != null ? ii(t, !!n, e, !0) : ii(t, !!n, n ? [] : "", !1));
        return;
      case "textarea":
        O = A = null;
        for (m in n)
          if (s = n[m], n.hasOwnProperty(m) && s != null && !a.hasOwnProperty(m))
            switch (m) {
              case "value":
                break;
              case "children":
                break;
              default:
                Ct(t, e, m, null, a, s);
            }
        for (f in a)
          if (s = a[f], u = n[f], a.hasOwnProperty(f) && (s != null || u != null))
            switch (f) {
              case "value":
                s !== u && (Tt = !0), A = s;
                break;
              case "defaultValue":
                s !== u && (Tt = !0), O = s;
                break;
              case "children":
                break;
              case "dangerouslySetInnerHTML":
                if (s != null) throw Error(o(91));
                break;
              default:
                s !== u && Ct(t, e, f, s, a, u);
            }
        Qh(t, A, O);
        return;
      case "option":
        for (var X in n)
          A = n[X], n.hasOwnProperty(X) && A != null && !a.hasOwnProperty(X) && (X === "selected" ? t.selected = !1 : Ct(
            t,
            e,
            X,
            null,
            a,
            A
          ));
        for (S in a)
          A = a[S], O = n[S], a.hasOwnProperty(S) && A !== O && (A != null || O != null) && (S === "selected" ? (A !== O && (Tt = !0), t.selected = A && typeof A != "function" && typeof A != "symbol") : Ct(
            t,
            e,
            S,
            A,
            a,
            O
          ));
        return;
      case "img":
      case "link":
      case "area":
      case "base":
      case "br":
      case "col":
      case "embed":
      case "hr":
      case "keygen":
      case "meta":
      case "param":
      case "source":
      case "track":
      case "wbr":
      case "menuitem":
        for (var P in n)
          A = n[P], n.hasOwnProperty(P) && A != null && !a.hasOwnProperty(P) && Ct(t, e, P, null, a, A);
        for (D in a)
          if (A = a[D], O = n[D], a.hasOwnProperty(D) && A !== O && (A != null || O != null))
            switch (D) {
              case "children":
              case "dangerouslySetInnerHTML":
                if (A != null)
                  throw Error(o(137, e));
                break;
              default:
                Ct(
                  t,
                  e,
                  D,
                  A,
                  a,
                  O
                );
            }
        return;
      default:
        if (Oo(e)) {
          for (var ot in n)
            A = n[ot], n.hasOwnProperty(ot) && A !== void 0 && !a.hasOwnProperty(ot) && Dc(
              t,
              e,
              ot,
              void 0,
              a,
              A
            );
          for (N in a)
            A = a[N], O = n[N], !a.hasOwnProperty(N) || A === O || A === void 0 && O === void 0 || Dc(
              t,
              e,
              N,
              A,
              a,
              O
            );
          return;
        }
    }
    for (var M in n)
      A = n[M], n.hasOwnProperty(M) && A != null && !a.hasOwnProperty(M) && Ct(t, e, M, null, a, A);
    for (w in a)
      A = a[w], O = n[w], !a.hasOwnProperty(w) || A === O || A == null && O == null || Ct(t, e, w, A, a, O);
  }
  function $y(t) {
    switch (t) {
      case "css":
      case "script":
      case "font":
      case "img":
      case "image":
      case "input":
      case "link":
        return !0;
      default:
        return !1;
    }
  }
  function rS() {
    if (typeof performance.getEntriesByType == "function") {
      for (var t = 0, e = 0, n = performance.getEntriesByType("resource"), a = 0; a < n.length; a++) {
        var s = n[a], u = s.transferSize, f = s.initiatorType, m = s.duration;
        if (u && m && $y(f)) {
          for (f = 0, m = s.responseEnd, a += 1; a < n.length; a++) {
            var S = n[a], D = S.startTime;
            if (D > m) break;
            var N = S.transferSize, w = S.initiatorType;
            N && $y(w) && (S = S.responseEnd, f += N * (S < m ? 1 : (m - D) / (S - D)));
          }
          if (--a, e += 8 * (u + f) / (s.duration / 1e3), t++, 10 < t) break;
        }
      }
      if (0 < t) return e / t / 1e6;
    }
    return navigator.connection && (t = navigator.connection.downlink, typeof t == "number") ? t : 5;
  }
  var Cc = null, Oc = null;
  function Hl(t) {
    return t.nodeType === 9 ? t : t.ownerDocument;
  }
  function tp(t) {
    switch (t) {
      case "http://www.w3.org/2000/svg":
        return 1;
      case "http://www.w3.org/1998/Math/MathML":
        return 2;
      default:
        return 0;
    }
  }
  function ep(t, e) {
    if (t === 0)
      switch (e) {
        case "svg":
          return 1;
        case "math":
          return 2;
        default:
          return 0;
      }
    return t === 1 && e === "foreignObject" ? 0 : t;
  }
  function np(t, e, n, a) {
    return n = Hl(
      n
    ).createElement(t), n[ie] = a, n[Te] = e, re(n, t, e), $t(n), n;
  }
  function Nc(t, e) {
    return t === "textarea" || t === "noscript" || typeof e.children == "string" || typeof e.children == "number" || typeof e.children == "bigint" || typeof e.dangerouslySetInnerHTML == "object" && e.dangerouslySetInnerHTML !== null && e.dangerouslySetInnerHTML.__html != null;
  }
  var zc = null;
  function cS() {
    var t = window.event;
    return t && t.type === "popstate" ? t === zc ? !1 : (zc = t, !0) : (zc = null, !1);
  }
  var Rc = typeof setTimeout == "function" ? setTimeout : void 0, fS = typeof clearTimeout == "function" ? clearTimeout : void 0, ap = typeof Promise == "function" ? Promise : void 0, ip = typeof requestAnimationFrame == "function" ? requestAnimationFrame : Rc, hS = typeof queueMicrotask == "function" ? queueMicrotask : typeof ap < "u" ? function(t) {
    return ap.resolve(null).then(t).catch(dS);
  } : Rc;
  function dS(t) {
    setTimeout(function() {
      throw t;
    });
  }
  function ca(t) {
    return t === "head";
  }
  function lp(t, e) {
    var n = e, a = 0;
    do {
      var s = n.nextSibling;
      if (t.removeChild(n), s && s.nodeType === 8)
        if (n = s.data, n === "/$" || n === "/&") {
          if (a === 0) {
            t.removeChild(s), Gi(e);
            return;
          }
          a--;
        } else if (n === "$" || n === "$?" || n === "$~" || n === "$!" || n === "&")
          a++;
        else if (n === "html")
          Lc(
            t.ownerDocument.documentElement
          );
        else if (n === "head") {
          n = t.ownerDocument.head, Lc(n);
          for (var u = n.firstChild; u; ) {
            var f = u.nextSibling, m = u.nodeName;
            u[nl] || m === "SCRIPT" || m === "STYLE" || m === "LINK" && u.rel.toLowerCase() === "stylesheet" || n.removeChild(u), u = f;
          }
        } else
          n === "body" && Lc(t.ownerDocument.body);
      n = s;
    } while (n);
    Gi(e);
  }
  function sp(t, e) {
    var n = t;
    t = 0;
    do {
      var a = n.nextSibling;
      if (n.nodeType === 1 ? e ? (n._stashedDisplay = n.style.display, n.style.display = "none") : (n.style.display = n._stashedDisplay || "", n.getAttribute("style") === "" && n.removeAttribute("style")) : n.nodeType === 3 && (e ? (n._stashedText = n.nodeValue, n.nodeValue = "") : n.nodeValue = n._stashedText || ""), a && a.nodeType === 8)
        if (n = a.data, n === "/$") {
          if (t === 0) break;
          t--;
        } else
          n !== "$" && n !== "$?" && n !== "$~" && n !== "$!" || t++;
      n = a;
    } while (n);
  }
  function up(t, e, n) {
    if (e = CSS.escape(e) !== e ? "r-" + btoa(e).replace(/=/g, "") : e, t.style.viewTransitionName = e, n != null && (t.style.viewTransitionClass = n), n = getComputedStyle(t), n.display === "inline") {
      if (e = t.getClientRects(), e.length === 1) var a = 1;
      else
        for (var s = a = 0; s < e.length; s++) {
          var u = e[s];
          0 < u.width && 0 < u.height && a++;
        }
      a === 1 && (t = t.style, t.display = e.length === 1 ? "inline-block" : "block", t.marginTop = "-" + n.paddingTop, t.marginBottom = "-" + n.paddingBottom);
    }
  }
  function op(t, e) {
    t = t.style, e = e.style;
    var n = e != null ? e.hasOwnProperty("viewTransitionName") ? e.viewTransitionName : e.hasOwnProperty("view-transition-name") ? e["view-transition-name"] : null : null;
    t.viewTransitionName = n == null || typeof n == "boolean" ? "" : ("" + n).trim(), n = e != null ? e.hasOwnProperty("viewTransitionClass") ? e.viewTransitionClass : e.hasOwnProperty("view-transition-class") ? e["view-transition-class"] : null : null, t.viewTransitionClass = n == null || typeof n == "boolean" ? "" : ("" + n).trim(), t.display === "inline-block" && (e == null ? t.display = t.margin = "" : (n = e.display, t.display = n == null || typeof n == "boolean" ? "" : n, n = e.margin, n != null ? t.margin = n : (n = e.hasOwnProperty("marginTop") ? e.marginTop : e["margin-top"], t.marginTop = n == null || typeof n == "boolean" ? "" : n, e = e.hasOwnProperty("marginBottom") ? e.marginBottom : e["margin-bottom"], t.marginBottom = e == null || typeof e == "boolean" ? "" : e)));
  }
  function mS(t, e, n) {
    return n = n.ownerDocument.defaultView, {
      rect: t,
      abs: e.position === "absolute" || e.position === "fixed",
      clip: e.clipPath !== "none" || e.overflow !== "visible" || e.filter !== "none" || e.mask !== "none" || e.mask !== "none" || e.borderRadius !== "0px",
      view: 0 <= t.bottom && 0 <= t.right && t.top <= n.innerHeight && t.left <= n.innerWidth
    };
  }
  function _c(t) {
    var e = t.getBoundingClientRect(), n = getComputedStyle(t);
    return mS(e, n, t);
  }
  function yS(t) {
    return t.documentElement.clientHeight;
  }
  function pS(t) {
    this.addEventListener("load", t), this.addEventListener("error", t);
  }
  function gS(t, e, n, a, s, u, f, m, S) {
    var D = e.nodeType === 9 ? e : e.ownerDocument;
    try {
      var N = D.startViewTransition({
        update: function() {
          var A = D.defaultView, O = A.navigation && A.navigation.transition, X = D.fonts.status;
          a();
          var P = [];
          if (X === "loaded" && (yS(D), D.fonts.status === "loading" && P.push(D.fonts.ready)), X = P.length, t !== null)
            for (var ot = t.suspenseyImages, M = 0, x = 0; x < ot.length; x++) {
              var C = ot[x];
              if (!C.complete) {
                var _ = C.getBoundingClientRect();
                if (0 < _.bottom && 0 < _.right && _.top < A.innerHeight && _.left < A.innerWidth) {
                  if (M += Np(C), M > Nu) {
                    P.length = X;
                    break;
                  }
                  C = new Promise(
                    pS.bind(C)
                  ), P.push(C);
                }
              }
            }
          if (0 < P.length)
            return A = Promise.race([
              Promise.all(P),
              new Promise(function(Z) {
                return setTimeout(Z, 500);
              })
            ]).then(s, s), (O ? Promise.allSettled([O.finished, A]) : A).then(u, u);
          if (s(), O)
            return O.finished.then(
              u,
              u
            );
          u();
        },
        types: n
      });
      D.__reactViewTransition = N;
      var w = [];
      return N.ready.then(
        function() {
          for (var A = D.documentElement.getAnimations({
            subtree: !0
          }), O = 0; O < A.length; O++) {
            var X = A[O], P = X.effect, ot = P.pseudoElement;
            if (ot != null && ot.startsWith("::view-transition")) {
              w.push(X), X = P.getKeyframes();
              for (var M = ot = void 0, x = !0, C = 0; C < X.length; C++) {
                var _ = X[C], Z = _.width;
                if (ot === void 0) ot = Z;
                else if (ot !== Z) {
                  x = !1;
                  break;
                }
                if (Z = _.height, M === void 0) M = Z;
                else if (M !== Z) {
                  x = !1;
                  break;
                }
                delete _.width, delete _.height, _.transform === "none" && delete _.transform;
              }
              x && ot !== void 0 && M !== void 0 && (P.setKeyframes(X), x = getComputedStyle(
                P.target,
                P.pseudoElement
              ), x.width !== ot || x.height !== M) && (x = X[0], x.width = ot, x.height = M, x = X[X.length - 1], x.width = ot, x.height = M, P.setKeyframes(X));
            }
          }
          f();
        },
        function(A) {
          D.__reactViewTransition === N && (D.__reactViewTransition = null);
          try {
            typeof A == "object" && A !== null && A.name === "InvalidStateError" && (A.message === "View transition was skipped because document visibility state is hidden." || A.message === "Skipping view transition because document visibility state has become hidden." || A.message === "Skipping view transition because viewport size changed." || A.message === "Transition was aborted because of invalid state") && (A = null), A !== null && S(A);
          } finally {
            a(), s(), f();
          }
        }
      ), N.finished.finally(function() {
        for (var A = 0; A < w.length; A++)
          w[A].cancel();
        D.__reactViewTransition === N && (D.__reactViewTransition = null), m();
      }), N;
    } catch {
      return a(), s(), f(), null;
    }
  }
  function Qa(t, e) {
    this._scope = document.documentElement, this._selector = "::view-transition-" + t + "(" + e + ")";
  }
  Qa.prototype.animate = function(t, e) {
    return e = typeof e == "number" ? { duration: e } : J({}, e), e.pseudoElement = this._selector, this._scope.animate(t, e);
  }, Qa.prototype.getAnimations = function() {
    for (var t = this._scope, e = this._selector, n = t.getAnimations({ subtree: !0 }), a = [], s = 0; s < n.length; s++) {
      var u = n[s].effect;
      u !== null && u.target === t && u.pseudoElement === e && a.push(n[s]);
    }
    return a;
  }, Qa.prototype.getComputedStyle = function() {
    return getComputedStyle(this._scope, this._selector);
  };
  function rp(t) {
    return {
      name: t,
      group: new Qa("group", t),
      imagePair: new Qa("image-pair", t),
      old: new Qa("old", t),
      new: new Qa("new", t)
    };
  }
  function Be(t) {
    this._fragmentFiber = t, this._observers = this._eventListeners = null;
  }
  Be.prototype.addEventListener = function(t, e, n) {
    var a = null, s = null;
    if (!(n != null && typeof n != "boolean" && (a = n.signal || null, a !== null && a.aborted))) {
      this._eventListeners === null && (this._eventListeners = []);
      var u = this._eventListeners;
      if (fp(u, t, e, n) === -1) {
        var f = this, m = e;
        n != null && typeof n != "boolean" && n.once === !0 && (m = function(S) {
          f.removeEventListener(
            t,
            e,
            n
          ), typeof e == "function" ? e.call(this, S) : e.handleEvent(S);
        }), a !== null && (s = f.removeEventListener.bind(
          f,
          t,
          e,
          n
        ), a.addEventListener("abort", s, { once: !0 }), s = a.removeEventListener.bind(a, "abort", s)), a = Ui(n), u.push({
          type: t,
          listener: e,
          optionsOrUseCapture: n,
          attachedListener: m,
          cleanup: s
        }), p(
          this._fragmentFiber.child,
          !1,
          vS,
          t,
          m,
          a
        );
      }
      this._eventListeners = u;
    }
  };
  function vS(t, e, n, a) {
    return j(t).addEventListener(
      e,
      n,
      a
    ), !1;
  }
  Be.prototype.removeEventListener = function(t, e, n) {
    var a = this._eventListeners;
    if (a !== null && (e = fp(
      a,
      t,
      e,
      n
    ), e !== -1)) {
      var s = a[e];
      n = s.attachedListener;
      var u = s.cleanup;
      s = Ui(s.optionsOrUseCapture), p(
        this._fragmentFiber.child,
        !1,
        bS,
        t,
        n,
        s
      ), a.splice(e, 1), u !== null && u();
    }
  };
  function bS(t, e, n, a) {
    return j(t).removeEventListener(
      e,
      n,
      a
    ), !1;
  }
  function Ui(t) {
    return t != null && typeof t != "boolean" && (t.once === !0 || t.signal instanceof AbortSignal) ? { capture: t.capture, passive: t.passive } : t;
  }
  function cp(t) {
    return t == null ? "c=0" : typeof t == "boolean" ? "c=" + (t ? "1" : "0") : "c=" + (t.capture ? "1" : "0");
  }
  function fp(t, e, n, a) {
    if (t.length === 0) return -1;
    a = cp(a);
    for (var s = 0; s < t.length; s++) {
      var u = t[s];
      if (u.type === e && u.listener === n && cp(u.optionsOrUseCapture) === a)
        return s;
    }
    return -1;
  }
  Be.prototype.dispatchEvent = function(t) {
    var e = T(
      this._fragmentFiber
    );
    if (e === null) return !0;
    e = j(e);
    var n = this._eventListeners;
    if (n !== null && 0 < n.length || !t.bubbles) {
      var a = e.nodeType === 9 ? e.createComment("") : document.createTextNode("");
      if (n)
        for (var s = 0; s < n.length; s++) {
          var u = n[s];
          a.addEventListener(
            u.type,
            u.attachedListener,
            Ui(u.optionsOrUseCapture)
          );
        }
      if (e.appendChild(a), t = a.dispatchEvent(t), n)
        for (s = 0; s < n.length; s++)
          u = n[s], a.removeEventListener(
            u.type,
            u.attachedListener,
            Ui(u.optionsOrUseCapture)
          );
      return e.removeChild(a), t;
    }
    return e.dispatchEvent(t);
  }, Be.prototype.focus = function(t) {
    p(
      this._fragmentFiber.child,
      !0,
      hp,
      t,
      void 0,
      void 0
    );
  };
  function hp(t, e) {
    return t.tag === 6 ? !1 : (t = j(t), RS(t, e));
  }
  Be.prototype.focusLast = function(t) {
    var e = [];
    p(
      this._fragmentFiber.child,
      !0,
      wc,
      e,
      void 0,
      void 0
    );
    for (var n = e.length - 1; 0 <= n && !hp(e[n], t); n--) ;
  };
  function wc(t, e) {
    return e.push(t), !1;
  }
  Be.prototype.blur = function() {
    var t = T(
      this._fragmentFiber
    );
    t !== null && (t = j(t), t = Hl(t).activeElement, t !== null && p(
      this._fragmentFiber.child,
      !1,
      SS,
      t,
      void 0,
      void 0
    ));
  };
  function SS(t, e) {
    return t.tag === 6 ? !1 : (t = j(t), t === e || t.contains(e) ? (e.blur(), !0) : !1);
  }
  Be.prototype.observeUsing = function(t) {
    this._observers === null && (this._observers = /* @__PURE__ */ new Set()), this._observers.add(t), p(
      this._fragmentFiber.child,
      !1,
      TS,
      t,
      void 0,
      void 0
    );
  };
  function TS(t, e) {
    return t.tag === 6 || (t = j(t), e.observe(t)), !1;
  }
  Be.prototype.unobserveUsing = function(t) {
    var e = this._observers;
    if (e !== null && e.has(t)) {
      e.delete(t), p(
        this._fragmentFiber.child,
        !1,
        xS,
        t,
        void 0,
        void 0
      );
      for (var n = e = 0; n < nn.length; n++) {
        var a = nn[n];
        a.fragmentInstance === this && a.observer === t ? t.unobserve(a.instance) : nn[e++] = a;
      }
      nn.length = e;
    }
  };
  function xS(t, e) {
    return t.tag === 6 || (t = j(t), e.unobserve(t)), !1;
  }
  var nn = [], Vc = !1;
  function ES(t, e, n) {
    nn.push({
      fragmentInstance: t,
      observer: e,
      instance: n
    }), Vc || (Vc = !0, _S(function() {
      Vc = !1;
      var a = nn;
      nn = [];
      for (var s = 0; s < a.length; s++) {
        var u = a[s];
        u.observer.unobserve(u.instance);
      }
    }));
  }
  Be.prototype.getClientRects = function() {
    var t = [];
    return p(
      this._fragmentFiber.child,
      !1,
      AS,
      t,
      void 0,
      void 0
    ), t;
  };
  function AS(t, e) {
    if (t.tag === 6) {
      t = t.stateNode;
      var n = t.ownerDocument.createRange();
      n.selectNodeContents(t), e.push.apply(e, n.getClientRects());
    } else
      t = j(t), e.push.apply(e, t.getClientRects());
    return !1;
  }
  Be.prototype.getRootNode = function(t) {
    var e = T(
      this._fragmentFiber
    );
    return e === null ? this : j(e).getRootNode(t);
  }, Be.prototype.compareDocumentPosition = function(t) {
    var e = T(
      this._fragmentFiber
    );
    if (e === null) return Node.DOCUMENT_POSITION_DISCONNECTED;
    var n = [];
    p(
      this._fragmentFiber.child,
      !1,
      wc,
      n,
      void 0,
      void 0
    );
    var a = j(e);
    if (n.length === 0) {
      if (n = a, V(this._fragmentFiber)) {
        t: {
          for (e = this._fragmentFiber.return; e !== null; ) {
            if (e.tag === 4) {
              e = e.stateNode.containerInfo;
              break t;
            }
            if (e.tag === 3 || e.tag === 5 || e.tag === 27)
              break;
            e = e.return;
          }
          e = null;
        }
        e != null && (n = e);
      }
      e = this._fragmentFiber;
      var s = a = n.compareDocumentPosition(t);
      return n === t ? s = Node.DOCUMENT_POSITION_CONTAINS : a & Node.DOCUMENT_POSITION_CONTAINED_BY && (n = z(e)[1], n === null ? s = Node.DOCUMENT_POSITION_PRECEDING : (t = j(n).compareDocumentPosition(
        t
      ), s = t === 0 || t & Node.DOCUMENT_POSITION_FOLLOWING ? Node.DOCUMENT_POSITION_FOLLOWING : Node.DOCUMENT_POSITION_PRECEDING)), s |= Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC;
    }
    e = j(n[0]), s = j(n[n.length - 1]);
    var u = V(this._fragmentFiber) ? e.parentElement : a;
    if (u == null)
      return Node.DOCUMENT_POSITION_DISCONNECTED;
    a = u.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_CONTAINED_BY, u = u.compareDocumentPosition(s) & Node.DOCUMENT_POSITION_CONTAINED_BY;
    var f = e.compareDocumentPosition(t), m = s.compareDocumentPosition(t), S = f & Node.DOCUMENT_POSITION_CONTAINED_BY || m & Node.DOCUMENT_POSITION_CONTAINED_BY;
    return m = a && u && f & Node.DOCUMENT_POSITION_FOLLOWING && m & Node.DOCUMENT_POSITION_PRECEDING, e = a && e === t || u && s === t || S || m ? Node.DOCUMENT_POSITION_CONTAINED_BY : !a && e === t || !u && s === t ? Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC : f, e & Node.DOCUMENT_POSITION_DISCONNECTED || e & Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC || MS(
      e,
      this._fragmentFiber,
      n[0],
      n[n.length - 1],
      t
    ) ? e : Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC;
  };
  function MS(t, e, n, a, s) {
    var u = Ea(s);
    if (t & Node.DOCUMENT_POSITION_CONTAINED_BY) {
      if (n = !!u)
        t: {
          for (; u !== null; ) {
            if (u.tag === 7 && (u === e || u.alternate === e)) {
              n = !0;
              break t;
            }
            u = u.return;
          }
          n = !1;
        }
      return n;
    }
    if (t & Node.DOCUMENT_POSITION_CONTAINS) {
      if (u === null)
        return u = s.ownerDocument, s === u || s === u.documentElement || s === u.body;
      t: {
        for (u = e, e = T(e); u !== null; ) {
          if (!(u.tag !== 5 && u.tag !== 3 && u.tag !== 27 || u !== e && u.alternate !== e)) {
            u = !0;
            break t;
          }
          u = u.return;
        }
        u = !1;
      }
      return u;
    }
    return t & Node.DOCUMENT_POSITION_PRECEDING ? ((e = !!u) && !(e = u === n) && (e = rt(
      n,
      u,
      nt
    ), e === null ? e = !1 : (p(
      e,
      !0,
      U,
      u,
      n
    ), u = L, L = null, e = u !== null)), e) : t & Node.DOCUMENT_POSITION_FOLLOWING ? ((e = !!u) && !(e = u === a) && (e = rt(
      a,
      u,
      nt
    ), e === null ? e = !1 : (p(
      e,
      !0,
      G,
      u,
      a
    ), u = L, Y = L = null, e = u !== null)), e) : !1;
  }
  function dp(t, e) {
    var n = t.ownerDocument.createRange();
    n.selectNodeContents(t), t = n.getBoundingClientRect(), window.scrollTo(
      window.scrollX + t.left,
      e ? window.scrollY + t.top : window.scrollY + t.bottom - window.innerHeight
    );
  }
  Be.prototype.scrollIntoView = function(t) {
    if (typeof t == "object") throw Error(o(566));
    var e = [];
    p(
      this._fragmentFiber.child,
      !1,
      wc,
      e,
      void 0,
      void 0
    );
    var n = t !== !1;
    if (e.length === 0) {
      var a = z(
        this._fragmentFiber
      );
      if (a = n ? a[1] || a[0] || T(this._fragmentFiber) : a[0] || a[1], a === null) return;
      if (a.tag === 6) {
        t = j(a), dp(t, n);
        return;
      }
      if (a = j(a), a.nodeType !== 9) {
        if (a.nodeType === 11) {
          n = "host" in a ? a.host : null, n !== null && n.scrollIntoView(t);
          return;
        }
        a.scrollIntoView(t);
      }
    }
    for (a = n ? e.length - 1 : 0; a !== (n ? -1 : e.length); ) {
      var s = e[a];
      s.tag === 6 ? (s = j(s), dp(s, n)) : j(s).scrollIntoView(t), a += n ? -1 : 1;
    }
  };
  function DS(t, e) {
    return t = j(t), mp(t, e), !1;
  }
  function mp(t, e) {
    t.reactFragments == null && (t.reactFragments = /* @__PURE__ */ new Set()), t.reactFragments.add(e);
  }
  function yp(t, e) {
    var n = e._eventListeners;
    if (n !== null)
      for (var a = 0; a < n.length; a++) {
        var s = n[a];
        t.addEventListener(
          s.type,
          s.attachedListener,
          Ui(s.optionsOrUseCapture)
        );
      }
    t.nodeType !== 3 && (n = e._observers, n !== null && n.forEach(function(u) {
      for (var f = 0, m = 0; m < nn.length; m++) {
        var S = nn[m];
        (S.fragmentInstance !== e || S.observer !== u || S.instance !== t) && (nn[f++] = S);
      }
      nn.length = f, u.observe(t);
    }), mp(t, e));
  }
  function CS(t, e) {
    var n = e._eventListeners;
    if (n !== null)
      for (var a = 0; a < n.length; a++) {
        var s = n[a];
        t.removeEventListener(
          s.type,
          s.attachedListener,
          Ui(s.optionsOrUseCapture)
        );
      }
    t.nodeType !== 3 && (n = e._observers, n !== null && n.forEach(function(u) {
      typeof u.rootMargin == "string" ? ES(
        e,
        u,
        t
      ) : u.unobserve(t);
    }), t.reactFragments != null && t.reactFragments.delete(e));
  }
  function jc(t) {
    var e = t.firstChild;
    for (e && e.nodeType === 10 && (e = e.nextSibling); e; ) {
      var n = e;
      switch (e = e.nextSibling, n.nodeName) {
        case "HTML":
        case "HEAD":
        case "BODY":
          jc(n), gs(n);
          continue;
        case "SCRIPT":
        case "STYLE":
          continue;
        case "LINK":
          if (n.rel.toLowerCase() === "stylesheet") continue;
      }
      t.removeChild(n);
    }
  }
  function OS(t, e, n, a) {
    for (; t.nodeType === 1; ) {
      var s = n;
      if (t.nodeName.toLowerCase() !== e.toLowerCase()) {
        if (!a && (t.nodeName !== "INPUT" || t.type !== "hidden"))
          break;
      } else if (a) {
        if (!t[nl])
          switch (e) {
            case "meta":
              if (!t.hasAttribute("itemprop")) break;
              return t;
            case "link":
              if (u = t.getAttribute("rel"), u === "stylesheet" && t.hasAttribute("data-precedence"))
                break;
              if (u !== s.rel || t.getAttribute("href") !== (s.href == null || s.href === "" ? null : s.href) || t.getAttribute("crossorigin") !== (s.crossOrigin == null ? null : s.crossOrigin) || t.getAttribute("title") !== (s.title == null ? null : s.title))
                break;
              return t;
            case "style":
              if (t.hasAttribute("data-precedence")) break;
              return t;
            case "script":
              if (u = t.getAttribute("src"), (u !== (s.src == null ? null : s.src) || t.getAttribute("type") !== (s.type == null ? null : s.type) || t.getAttribute("crossorigin") !== (s.crossOrigin == null ? null : s.crossOrigin)) && u && t.hasAttribute("async") && !t.hasAttribute("itemprop"))
                break;
              return t;
            default:
              return t;
          }
      } else if (e === "input" && t.type === "hidden") {
        var u = s.name == null ? null : "" + s.name;
        if (s.type === "hidden" && t.getAttribute("name") === u)
          return t;
      } else return t;
      if (t = Ke(t.nextSibling), t === null) break;
    }
    return null;
  }
  function NS(t, e, n) {
    if (e === "") return null;
    for (; t.nodeType !== 3; )
      if ((t.nodeType !== 1 || t.nodeName !== "INPUT" || t.type !== "hidden") && !n || (t = Ke(t.nextSibling), t === null)) return null;
    return t;
  }
  function pp(t, e) {
    for (; t.nodeType !== 8; )
      if ((t.nodeType !== 1 || t.nodeName !== "INPUT" || t.type !== "hidden") && !e || (t = Ke(t.nextSibling), t === null)) return null;
    return t;
  }
  function Uc(t) {
    return t.data === "$?" || t.data === "$~";
  }
  function Bc(t) {
    return t.data === "$!" || t.data === "$?" && t.ownerDocument.readyState !== "loading";
  }
  function zS(t, e) {
    var n = t.ownerDocument;
    if (t.data === "$~") t._reactRetry = e;
    else if (t.data !== "$?" || n.readyState !== "loading")
      e();
    else {
      var a = function() {
        e(), n.removeEventListener("DOMContentLoaded", a);
      };
      n.addEventListener("DOMContentLoaded", a), t._reactRetry = a;
    }
  }
  function Ke(t) {
    for (; t != null; t = t.nextSibling) {
      var e = t.nodeType;
      if (e === 1 || e === 3) break;
      if (e === 8) {
        if (e = t.data, e === "$" || e === "$!" || e === "$?" || e === "$~" || e === "&" || e === "F!" || e === "F")
          break;
        if (e === "/$" || e === "/&") return null;
      }
    }
    return t;
  }
  var Hc = null;
  function gp(t) {
    t = t.nextSibling;
    for (var e = 0; t; ) {
      if (t.nodeType === 8) {
        var n = t.data;
        if (n === "/$" || n === "/&") {
          if (e === 0)
            return Ke(t.nextSibling);
          e--;
        } else
          n !== "$" && n !== "$!" && n !== "$?" && n !== "$~" && n !== "&" || e++;
      }
      t = t.nextSibling;
    }
    return null;
  }
  function vp(t) {
    t = t.previousSibling;
    for (var e = 0; t; ) {
      if (t.nodeType === 8) {
        var n = t.data;
        if (n === "$" || n === "$!" || n === "$?" || n === "$~" || n === "&") {
          if (e === 0) return t;
          e--;
        } else n !== "/$" && n !== "/&" || e++;
      }
      t = t.previousSibling;
    }
    return null;
  }
  function RS(t, e) {
    function n() {
      a = !0;
    }
    if (t.ownerDocument.activeElement === t) return !0;
    var a = !1;
    try {
      t.ownerDocument.addEventListener("focus", n, !0), (t.focus || HTMLElement.prototype.focus).call(t, e);
    } finally {
      t.ownerDocument.removeEventListener("focus", n, !0);
    }
    return a;
  }
  function _S(t) {
    ip(function() {
      ip(function(e) {
        return t(e);
      });
    });
  }
  function bp(t, e, n) {
    switch (e = Hl(n), t) {
      case "html":
        if (t = e.documentElement, !t) throw Error(o(452));
        return t;
      case "head":
        if (t = e.head, !t) throw Error(o(453));
        return t;
      case "body":
        if (t = e.body, !t) throw Error(o(454));
        return t;
      default:
        throw Error(o(451));
    }
  }
  function Sp(t, e, n) {
    for (var a in n) {
      var s = n[a];
      n.hasOwnProperty(a) && s != null && Ct(t, e, a, null, uS, s);
    }
    n.dangerouslySetInnerHTML != null && (t.textContent = ""), t.onclick === rn && (t.onclick = null), gs(t);
  }
  function Lc(t) {
    for (var e = t.attributes; e.length; )
      t.removeAttributeNode(e[0]);
    gs(t);
  }
  var Je = /* @__PURE__ */ new Map(), Tp = /* @__PURE__ */ new Set();
  function Ll(t) {
    if (typeof t.getRootNode == "function") {
      var e = t.getRootNode();
      if (e.nodeType === 9 || e.nodeType === 11) return e;
    }
    return t.nodeType === 9 ? t : t.ownerDocument;
  }
  var Ln = lt.d;
  lt.d = {
    f: wS,
    r: VS,
    D: jS,
    C: US,
    L: BS,
    m: HS,
    X: YS,
    S: LS,
    M: qS
  };
  function wS() {
    var t = Ln.f(), e = Su();
    return t || e;
  }
  function VS(t) {
    var e = ei(t);
    e !== null && e.tag === 5 && e.type === "form" ? Em(e) : Ln.r(t);
  }
  var Bi = typeof document > "u" ? null : document;
  function xp(t, e, n) {
    var a = Bi;
    if (a && typeof e == "string" && e) {
      var s = Le(e);
      s = 'link[rel="' + t + '"][href="' + s + '"]', typeof n == "string" && (s += '[crossorigin="' + n + '"]'), Tp.has(s) || (Tp.add(s), t = { rel: t, crossOrigin: n, href: e }, a.querySelector(s) === null && (e = a.createElement("link"), re(e, "link", t), $t(e), a.head.appendChild(e)));
    }
  }
  function jS(t) {
    Ln.D(t), xp("dns-prefetch", t, null);
  }
  function US(t, e) {
    Ln.C(t, e), xp("preconnect", t, e);
  }
  function BS(t, e, n) {
    Ln.L(t, e, n);
    var a = Bi;
    if (a && t && e) {
      var s = 'link[rel="preload"][as="' + Le(e) + '"]';
      e === "image" && n && n.imageSrcSet ? (s += '[imagesrcset="' + Le(
        n.imageSrcSet
      ) + '"]', typeof n.imageSizes == "string" && (s += '[imagesizes="' + Le(
        n.imageSizes
      ) + '"]')) : s += '[href="' + Le(t) + '"]';
      var u = s;
      switch (e) {
        case "style":
          u = Hi(t);
          break;
        case "script":
          u = Li(t);
      }
      if (!(Je.has(u) || (t = J(
        {
          rel: "preload",
          href: e === "image" && n && n.imageSrcSet ? void 0 : t,
          as: e
        },
        n
      ), Je.set(u, t), a.querySelector(s) !== null || e === "style" && a.querySelector(Yl(u)) || e === "script" && a.querySelector(ql(u))))) {
        var f = a.createElement("link");
        re(f, "link", t), e === "style" && (f[ps] = !0, f.onload = f.onerror = function() {
          jh(f);
        }), $t(f), a.head.appendChild(f);
      }
    }
  }
  function HS(t, e) {
    Ln.m(t, e);
    var n = Bi;
    if (n && t) {
      var a = e && typeof e.as == "string" ? e.as : "script", s = 'link[rel="modulepreload"][as="' + Le(a) + '"][href="' + Le(t) + '"]', u = s;
      switch (a) {
        case "audioworklet":
        case "paintworklet":
        case "serviceworker":
        case "sharedworker":
        case "worker":
        case "script":
          u = Li(t);
      }
      if (!Je.has(u) && (t = J({ rel: "modulepreload", href: t }, e), Je.set(u, t), n.querySelector(s) === null)) {
        switch (a) {
          case "audioworklet":
          case "paintworklet":
          case "serviceworker":
          case "sharedworker":
          case "worker":
          case "script":
            if (n.querySelector(ql(u)))
              return;
        }
        a = n.createElement("link"), re(a, "link", t), $t(a), n.head.appendChild(a);
      }
    }
  }
  function LS(t, e, n) {
    Ln.S(t, e, n);
    var a = Bi;
    if (a && t) {
      var s = ni(a).hoistableStyles, u = Hi(t);
      e = e || "default";
      var f = s.get(u);
      if (!f) {
        var m = { loading: 0, preload: null };
        if (f = a.querySelector(
          Yl(u)
        ))
          m.loading = 5;
        else {
          t = J(
            { rel: "stylesheet", href: t, "data-precedence": e },
            n
          ), (n = Je.get(u)) && Yc(t, n);
          var S = f = a.createElement("link");
          $t(S), re(S, "link", t), S._p = new Promise(function(D, N) {
            S.onload = D, S.onerror = N;
          }), S.addEventListener("load", function() {
            m.loading |= 1;
          }), S.addEventListener("error", function() {
            m.loading |= 2;
          }), m.loading |= 4, Cu(f, e, a);
        }
        f = {
          type: "stylesheet",
          instance: f,
          count: 1,
          state: m
        }, s.set(u, f);
      }
    }
  }
  function YS(t, e) {
    Ln.X(t, e);
    var n = Bi;
    if (n && t) {
      var a = ni(n).hoistableScripts, s = Li(t), u = a.get(s);
      u || (u = n.querySelector(ql(s)), u || (t = J({ src: t, async: !0 }, e), (e = Je.get(s)) && qc(t, e), u = n.createElement("script"), $t(u), re(u, "link", t), n.head.appendChild(u)), u = {
        type: "script",
        instance: u,
        count: 1,
        state: null
      }, a.set(s, u));
    }
  }
  function qS(t, e) {
    Ln.M(t, e);
    var n = Bi;
    if (n && t) {
      var a = ni(n).hoistableScripts, s = Li(t), u = a.get(s);
      u || (u = n.querySelector(ql(s)), u || (t = J({ src: t, async: !0, type: "module" }, e), (e = Je.get(s)) && qc(t, e), u = n.createElement("script"), $t(u), re(u, "link", t), n.head.appendChild(u)), u = {
        type: "script",
        instance: u,
        count: 1,
        state: null
      }, a.set(s, u));
    }
  }
  function Ep(t, e, n, a) {
    var s = (s = qn.current) ? Ll(s) : null;
    if (!s) throw Error(o(446));
    switch (t) {
      case "meta":
      case "title":
        return null;
      case "style":
        return typeof n.precedence == "string" && typeof n.href == "string" ? (n = Hi(n.href), e = ni(
          s
        ).hoistableStyles, a = e.get(n), a || (a = {
          type: "style",
          instance: null,
          count: 0,
          state: null
        }, e.set(n, a)), a) : { type: "void", instance: null, count: 0, state: null };
      case "link":
        if (n.rel === "stylesheet" && typeof n.href == "string" && typeof n.precedence == "string") {
          t = Hi(n.href);
          var u = ni(
            s
          ).hoistableStyles, f = u.get(t);
          if (f || (s = s.ownerDocument || s, f = {
            type: "stylesheet",
            instance: null,
            count: 0,
            state: { loading: 0, preload: null }
          }, u.set(t, f), (u = s.querySelector(
            Yl(t)
          )) ? u._p || (f.instance = u, f.state.loading = 5) : (u = Je.get(t), u || (u = {
            rel: "preload",
            as: "style",
            href: n.href,
            crossOrigin: n.crossOrigin,
            integrity: n.integrity,
            media: n.media,
            hrefLang: n.hrefLang,
            referrerPolicy: n.referrerPolicy
          }, Je.set(t, u)), GS(
            s,
            t,
            u,
            f.state
          ))), e && a === null)
            throw Error(o(528, ""));
          return f;
        }
        if (e && a !== null)
          throw Error(o(529, ""));
        return null;
      case "script":
        return e = n.async, n = n.src, typeof n == "string" && e && typeof e != "function" && typeof e != "symbol" ? (n = Li(n), e = ni(
          s
        ).hoistableScripts, a = e.get(n), a || (a = {
          type: "script",
          instance: null,
          count: 0,
          state: null
        }, e.set(n, a)), a) : { type: "void", instance: null, count: 0, state: null };
      default:
        throw Error(o(444, t));
    }
  }
  function Hi(t) {
    return 'href="' + Le(t) + '"';
  }
  function Yl(t) {
    return 'link[rel="stylesheet"][' + t + "]";
  }
  function Ap(t) {
    return J({}, t, {
      "data-precedence": t.precedence,
      precedence: null
    });
  }
  function GS(t, e, n, a) {
    if (e = t.querySelector(
      'link[rel="preload"][as="style"][' + e + "]"
    )) {
      if (e[ps] !== !0) {
        a.loading = 1;
        return;
      }
    } else
      e = t.createElement("link"), e[ps] = !0, e.onload = e.onerror = jh.bind(null, e), re(e, "link", n), $t(e), t.head.appendChild(e);
    a.preload = e, e.addEventListener("load", function() {
      return a.loading |= 1;
    }), e.addEventListener("error", function() {
      return a.loading |= 2;
    });
  }
  function Li(t) {
    return '[src="' + Le(t) + '"]';
  }
  function ql(t) {
    return "script[async]" + t;
  }
  function Mp(t, e, n) {
    if (e.count++, e.instance === null)
      switch (e.type) {
        case "style":
          var a = t.querySelector(
            'style[data-href~="' + Le(n.href) + '"]'
          );
          if (a)
            return e.instance = a, $t(a), a;
          var s = J({}, n, {
            "data-href": n.href,
            "data-precedence": n.precedence,
            href: null,
            precedence: null
          });
          return a = (t.ownerDocument || t).createElement(
            "style"
          ), $t(a), re(a, "style", s), Cu(a, n.precedence, t), e.instance = a;
        case "stylesheet":
          s = Hi(n.href);
          var u = t.querySelector(
            Yl(s)
          );
          if (u)
            return e.state.loading |= 4, e.instance = u, $t(u), u;
          a = Ap(n), (s = Je.get(s)) && Yc(a, s), u = (t.ownerDocument || t).createElement("link"), $t(u);
          var f = u;
          return f._p = new Promise(function(m, S) {
            f.onload = m, f.onerror = S;
          }), re(u, "link", a), e.state.loading |= 4, Cu(u, n.precedence, t), e.instance = u;
        case "script":
          return u = Li(n.src), (s = t.querySelector(
            ql(u)
          )) ? (e.instance = s, $t(s), s) : (a = n, (s = Je.get(u)) && (a = J({}, n), qc(a, s)), t = t.ownerDocument || t, s = t.createElement("script"), $t(s), re(s, "link", a), t.head.appendChild(s), e.instance = s);
        case "void":
          return null;
        default:
          throw Error(o(443, e.type));
      }
    else
      e.type === "stylesheet" && (e.state.loading & 4) === 0 && (a = e.instance, e.state.loading |= 4, Cu(a, n.precedence, t));
    return e.instance;
  }
  function Cu(t, e, n) {
    for (var a = n.querySelectorAll(
      'link[rel="stylesheet"][data-precedence],style[data-precedence]'
    ), s = a.length ? a[a.length - 1] : null, u = s, f = 0; f < a.length; f++) {
      var m = a[f];
      if (m.dataset.precedence === e) u = m;
      else if (u !== s) break;
    }
    u ? u.parentNode.insertBefore(t, u.nextSibling) : (e = n.nodeType === 9 ? n.head : n, e.insertBefore(t, e.firstChild));
  }
  function Yc(t, e) {
    t.crossOrigin == null && (t.crossOrigin = e.crossOrigin), t.referrerPolicy == null && (t.referrerPolicy = e.referrerPolicy), t.title == null && (t.title = e.title);
  }
  function qc(t, e) {
    t.crossOrigin == null && (t.crossOrigin = e.crossOrigin), t.referrerPolicy == null && (t.referrerPolicy = e.referrerPolicy), t.integrity == null && (t.integrity = e.integrity);
  }
  var Ou = null;
  function Dp(t, e, n) {
    if (Ou === null) {
      var a = /* @__PURE__ */ new Map(), s = Ou = /* @__PURE__ */ new Map();
      s.set(n, a);
    } else
      s = Ou, a = s.get(n), a || (a = /* @__PURE__ */ new Map(), s.set(n, a));
    if (a.has(t)) return a;
    for (a.set(t, null), n = n.getElementsByTagName(t), s = 0; s < n.length; s++) {
      var u = n[s];
      if (!(u[nl] || u[ie] || t === "link" && u.getAttribute("rel") === "stylesheet") && u.namespaceURI !== "http://www.w3.org/2000/svg") {
        var f = u.getAttribute(e) || "";
        f = t + f;
        var m = a.get(f);
        m ? m.push(u) : a.set(f, [u]);
      }
    }
    return a;
  }
  function Gc(t, e, n) {
    t = t.ownerDocument || t, t.head.insertBefore(
      n,
      e === "title" ? t.querySelector("head > title") : null
    );
  }
  function XS(t, e, n) {
    if (n === 1 || e.itemProp != null) return !1;
    switch (t) {
      case "meta":
      case "title":
        return !0;
      case "style":
        if (typeof e.precedence != "string" || typeof e.href != "string" || e.href === "")
          break;
        return !0;
      case "link":
        if (typeof e.rel != "string" || typeof e.href != "string" || e.href === "" || e.onLoad || e.onError)
          break;
        return e.rel === "stylesheet" ? (t = e.disabled, typeof e.precedence == "string" && t == null) : !0;
      case "script":
        if (e.async && typeof e.async != "function" && typeof e.async != "symbol" && !e.onLoad && !e.onError && e.src && typeof e.src == "string")
          return !0;
    }
    return !1;
  }
  function Cp(t, e) {
    return t === "img" && e.src != null && e.src !== "" && e.onLoad == null && e.loading !== "lazy";
  }
  function Op(t) {
    return !(t.type === "stylesheet" && (t.state.loading & 3) === 0);
  }
  function Np(t) {
    return (t.width || 100) * (t.height || 100) * (typeof devicePixelRatio == "number" ? devicePixelRatio : 1) * 0.25;
  }
  function zp(t, e) {
    typeof e.decode == "function" && (t.imgCount++, e.complete || (t.imgBytes += Np(e), t.suspenseyImages.push(e)), t = KS.bind(t), e.decode().then(t, t));
  }
  function QS(t, e, n, a) {
    if (n.type === "stylesheet" && (typeof a.media != "string" || matchMedia(a.media).matches !== !1) && (n.state.loading & 4) === 0) {
      if (n.instance === null) {
        var s = Hi(a.href), u = e.querySelector(
          Yl(s)
        );
        if (u) {
          e = u._p, e !== null && typeof e == "object" && typeof e.then == "function" && (t.count++, t = Gl.bind(t), e.then(t, t)), n.state.loading |= 4, n.instance = u, $t(u);
          return;
        }
        u = e.ownerDocument || e, a = Ap(a), (s = Je.get(s)) && Yc(a, s), u = u.createElement("link"), $t(u);
        var f = u;
        f._p = new Promise(function(m, S) {
          f.onload = m, f.onerror = S;
        }), re(u, "link", a), n.instance = u;
      }
      t.stylesheets === null && (t.stylesheets = /* @__PURE__ */ new Map()), t.stylesheets.set(n, e), (e = n.state.preload) && (n.state.loading & 3) === 0 && (t.count++, n = Gl.bind(t), e.addEventListener("load", n), e.addEventListener("error", n));
    }
  }
  var Nu = 0;
  function ZS(t, e) {
    return t.stylesheets && t.count === 0 && Ru(t, t.stylesheets), 0 < t.count || 0 < t.imgCount ? function(n) {
      var a = setTimeout(function() {
        if (t.stylesheets && Ru(t, t.stylesheets), t.unsuspend) {
          var u = t.unsuspend;
          t.unsuspend = null, u();
        }
      }, 6e4 + e);
      0 < t.imgBytes && Nu === 0 && (Nu = 62500 * rS());
      var s = setTimeout(
        function() {
          if (t.waitingForImages = !1, t.count === 0 && (t.stylesheets && Ru(t, t.stylesheets), t.unsuspend)) {
            var u = t.unsuspend;
            t.unsuspend = null, u();
          }
        },
        (t.imgBytes > Nu ? 50 : 800) + e
      );
      return t.unsuspend = n, function() {
        t.unsuspend = null, clearTimeout(a), clearTimeout(s);
      };
    } : null;
  }
  function Rp(t) {
    if (t.count === 0 && (t.imgCount === 0 || !t.waitingForImages)) {
      if (t.stylesheets) Ru(t, t.stylesheets);
      else if (t.unsuspend) {
        var e = t.unsuspend;
        t.unsuspend = null, e();
      }
    }
  }
  function Gl() {
    this.count--, Rp(this);
  }
  function KS() {
    this.imgCount--, Rp(this);
  }
  var zu = null;
  function Ru(t, e) {
    t.stylesheets = null, t.unsuspend !== null && (t.count++, zu = /* @__PURE__ */ new Map(), e.forEach(JS, t), zu = null, Gl.call(t));
  }
  function JS(t, e) {
    if (!(e.state.loading & 4)) {
      var n = zu.get(t);
      if (n) var a = n.get(null);
      else {
        n = /* @__PURE__ */ new Map(), zu.set(t, n);
        for (var s = t.querySelectorAll(
          "link[data-precedence],style[data-precedence]"
        ), u = 0; u < s.length; u++) {
          var f = s[u];
          (f.nodeName === "LINK" || f.getAttribute("media") !== "not all") && (n.set(f.dataset.precedence, f), a = f);
        }
        a && n.set(null, a);
      }
      s = e.instance, f = s.getAttribute("data-precedence"), u = n.get(f) || a, u === a && n.set(null, s), n.set(f, s), this.count++, a = Gl.bind(this), s.addEventListener("load", a), s.addEventListener("error", a), u ? u.parentNode.insertBefore(s, u.nextSibling) : (t = t.nodeType === 9 ? t.head : t, t.insertBefore(s, t.firstChild)), e.state.loading |= 4;
    }
  }
  var Yi = {
    $$typeof: zt,
    Provider: null,
    Consumer: null,
    _currentValue: An,
    _currentValue2: An,
    _threadCount: 0
  };
  function kS(t, e, n, a, s, u, f, m, S) {
    this.tag = 1, this.containerInfo = t, this.pingCache = this.current = this.pendingChildren = null, this.timeoutHandle = -1, this.callbackNode = this.next = this.pendingContext = this.context = this.cancelPendingCommit = null, this.callbackPriority = 0, this.expirationTimes = xo(-1), this.entangledLanes = this.shellSuspendCounter = this.errorRecoveryDisabledLanes = this.expiredLanes = this.warmLanes = this.pingedLanes = this.suspendedLanes = this.pendingLanes = 0, this.entanglements = xo(0), this.hiddenUpdates = xo(null), this.identifierPrefix = a, this.onUncaughtError = s, this.onCaughtError = u, this.onRecoverableError = f, this.pooledCache = null, this.pooledCacheLanes = 0, this.formState = S, this.transitionTypes = null, this.incompleteTransitions = /* @__PURE__ */ new Map();
  }
  function _p(t, e, n, a, s, u, f, m, S, D, N, w) {
    return t = new kS(
      t,
      e,
      n,
      f,
      S,
      D,
      N,
      w,
      m
    ), e = 1, u === !0 && (e |= 24), u = xe(3, null, null, e), t.current = u, u.stateNode = t, e = ar(), e.refCount++, t.pooledCache = e, e.refCount++, u.memoizedState = {
      element: a,
      isDehydrated: n,
      cache: e
    }, ur(u), t;
  }
  function wp(t) {
    return t ? (t = hi, t) : hi;
  }
  function Vp(t, e, n, a, s, u) {
    s = wp(s), a.context === null ? a.context = s : a.pendingContext = s, a = In(e), a.payload = { element: n }, u = u === void 0 ? null : u, u !== null && (a.callback = u), n = $n(t, a, e), n !== null && (De(n, t, e), bl(n, t, e));
  }
  function jp(t, e) {
    if (t = t.memoizedState, t !== null && t.dehydrated !== null) {
      var n = t.retryLane;
      t.retryLane = n !== 0 && n < e ? n : e;
    }
  }
  function Xc(t, e) {
    jp(t, e), (t = t.alternate) && jp(t, e);
  }
  function Up(t) {
    if (t.tag === 13 || t.tag === 31) {
      var e = Ca(t, 67108864);
      e !== null && De(e, t, 67108864), Xc(t, 67108864);
    }
  }
  function Bp(t) {
    if (t.tag === 13 || t.tag === 31) {
      var e = Ue();
      e = Eo(e);
      var n = Ca(t, e);
      n !== null && De(n, t, e), Xc(t, e);
    }
  }
  var qi = !0;
  function PS(t, e, n, a) {
    var s = W.T;
    W.T = null;
    var u = lt.p;
    try {
      lt.p = 2, Qc(t, e, n, a);
    } finally {
      lt.p = u, W.T = s;
    }
  }
  function FS(t, e, n, a) {
    var s = W.T;
    W.T = null;
    var u = lt.p;
    try {
      lt.p = 8, Qc(t, e, n, a);
    } finally {
      lt.p = u, W.T = s;
    }
  }
  function Qc(t, e, n, a) {
    if (qi) {
      var s = Zc(a);
      if (s === null)
        Mc(
          t,
          e,
          a,
          _u,
          n
        ), Lp(t, a);
      else if (IS(
        s,
        t,
        e,
        n,
        a
      ))
        a.stopPropagation();
      else if (Lp(t, a), e & 4 && -1 < WS.indexOf(t)) {
        for (; s !== null; ) {
          var u = ei(s);
          if (u !== null)
            switch (u.tag) {
              case 3:
                if (u = u.stateNode, u.current.memoizedState.isDehydrated) {
                  var f = xa(u.pendingLanes);
                  if (f !== 0) {
                    var m = u;
                    for (m.pendingLanes |= 2, m.entangledLanes |= 2; f; ) {
                      var S = 1 << 31 - Ne(f);
                      m.entanglements[1] |= S, f &= ~S;
                    }
                    bn(u), (Et & 6) === 0 && (gu = Ce() + 500, jl(0));
                  }
                }
                break;
              case 31:
              case 13:
                m = Ca(u, 2), m !== null && De(m, u, 2), Su(), Xc(u, 2);
            }
          if (u = Zc(a), u === null && Mc(
            t,
            e,
            a,
            _u,
            n
          ), u === s) break;
          s = u;
        }
        s !== null && a.stopPropagation();
      } else
        Mc(
          t,
          e,
          a,
          null,
          n
        );
    }
  }
  function Zc(t) {
    return t = zo(t), Kc(t);
  }
  var _u = null;
  function Kc(t) {
    if (_u = null, t = Ea(t), t !== null) {
      var e = d(t);
      if (e === null) t = null;
      else {
        var n = e.tag;
        if (n === 13) {
          if (t = h(e), t !== null) return t;
          t = null;
        } else if (n === 31) {
          if (t = y(e), t !== null) return t;
          t = null;
        } else if (n === 3) {
          if (e.stateNode.current.memoizedState.isDehydrated)
            return e.tag === 3 ? e.stateNode.containerInfo : null;
          t = null;
        } else e !== t && (t = null);
      }
    }
    return _u = t, null;
  }
  function Hp(t) {
    switch (t) {
      case "beforetoggle":
      case "cancel":
      case "click":
      case "close":
      case "contextmenu":
      case "copy":
      case "cut":
      case "auxclick":
      case "dblclick":
      case "dragend":
      case "dragstart":
      case "drop":
      case "focusin":
      case "focusout":
      case "input":
      case "invalid":
      case "keydown":
      case "keypress":
      case "keyup":
      case "mousedown":
      case "mouseup":
      case "paste":
      case "pause":
      case "play":
      case "pointercancel":
      case "pointerdown":
      case "pointerup":
      case "ratechange":
      case "reset":
      case "seeked":
      case "submit":
      case "toggle":
      case "touchcancel":
      case "touchend":
      case "touchstart":
      case "volumechange":
      case "change":
      case "selectionchange":
      case "textInput":
      case "compositionstart":
      case "compositionend":
      case "compositionupdate":
      case "beforeblur":
      case "afterblur":
      case "beforeinput":
      case "blur":
      case "fullscreenchange":
      case "fullscreenerror":
      case "focus":
      case "hashchange":
      case "popstate":
      case "select":
      case "selectstart":
        return 2;
      case "drag":
      case "dragenter":
      case "dragexit":
      case "dragleave":
      case "dragover":
      case "mousemove":
      case "mouseout":
      case "mouseover":
      case "pointermove":
      case "pointerout":
      case "pointerover":
      case "resize":
      case "scroll":
      case "touchmove":
      case "wheel":
      case "mouseenter":
      case "mouseleave":
      case "pointerenter":
      case "pointerleave":
        return 8;
      case "message":
        switch (r1()) {
          case Eh:
            return 2;
          case Ah:
            return 8;
          case fs:
          case c1:
            return 32;
          case Mh:
            return 268435456;
          default:
            return 32;
        }
      default:
        return 32;
    }
  }
  var Jc = !1, fa = null, ha = null, da = null, Xl = /* @__PURE__ */ new Map(), Ql = /* @__PURE__ */ new Map(), ma = [], WS = "mousedown mouseup touchcancel touchend touchstart auxclick dblclick pointercancel pointerdown pointerup dragend dragstart drop compositionend compositionstart keydown keypress keyup input textInput copy cut paste click change contextmenu reset".split(
    " "
  );
  function Lp(t, e) {
    switch (t) {
      case "focusin":
      case "focusout":
        fa = null;
        break;
      case "dragenter":
      case "dragleave":
        ha = null;
        break;
      case "mouseover":
      case "mouseout":
        da = null;
        break;
      case "pointerover":
      case "pointerout":
        Xl.delete(e.pointerId);
        break;
      case "gotpointercapture":
      case "lostpointercapture":
        Ql.delete(e.pointerId);
    }
  }
  function Zl(t, e, n, a, s, u) {
    return t === null || t.nativeEvent !== u ? (t = {
      blockedOn: e,
      domEventName: n,
      eventSystemFlags: a,
      nativeEvent: u,
      targetContainers: [s]
    }, e !== null && (e = ei(e), e !== null && Up(e)), t) : (t.eventSystemFlags |= a, e = t.targetContainers, s !== null && e.indexOf(s) === -1 && e.push(s), t);
  }
  function IS(t, e, n, a, s) {
    switch (e) {
      case "focusin":
        return fa = Zl(
          fa,
          t,
          e,
          n,
          a,
          s
        ), !0;
      case "dragenter":
        return ha = Zl(
          ha,
          t,
          e,
          n,
          a,
          s
        ), !0;
      case "mouseover":
        return da = Zl(
          da,
          t,
          e,
          n,
          a,
          s
        ), !0;
      case "pointerover":
        var u = s.pointerId;
        return Xl.set(
          u,
          Zl(
            Xl.get(u) || null,
            t,
            e,
            n,
            a,
            s
          )
        ), !0;
      case "gotpointercapture":
        return u = s.pointerId, Ql.set(
          u,
          Zl(
            Ql.get(u) || null,
            t,
            e,
            n,
            a,
            s
          )
        ), !0;
    }
    return !1;
  }
  function Yp(t) {
    var e = Ea(t.target);
    if (e !== null) {
      var n = d(e);
      if (n !== null) {
        if (e = n.tag, e === 13) {
          if (e = h(n), e !== null) {
            t.blockedOn = e, _h(t.priority, function() {
              Bp(n);
            });
            return;
          }
        } else if (e === 31) {
          if (e = y(n), e !== null) {
            t.blockedOn = e, _h(t.priority, function() {
              Bp(n);
            });
            return;
          }
        } else if (e === 3 && n.stateNode.current.memoizedState.isDehydrated) {
          t.blockedOn = n.tag === 3 ? n.stateNode.containerInfo : null;
          return;
        }
      }
    }
    t.blockedOn = null;
  }
  function wu(t) {
    if (t.blockedOn !== null) return !1;
    for (var e = t.targetContainers; 0 < e.length; ) {
      var n = Zc(t.nativeEvent);
      if (n === null) {
        n = t.nativeEvent;
        var a = new n.constructor(
          n.type,
          n
        );
        No = a, n.target.dispatchEvent(a), No = null;
      } else
        return e = ei(n), e !== null && Up(e), t.blockedOn = n, !1;
      e.shift();
    }
    return !0;
  }
  function qp(t, e, n) {
    wu(t) && n.delete(e);
  }
  function $S() {
    Jc = !1, fa !== null && wu(fa) && (fa = null), ha !== null && wu(ha) && (ha = null), da !== null && wu(da) && (da = null), Xl.forEach(qp), Ql.forEach(qp);
  }
  function Vu(t, e) {
    t.blockedOn === e && (t.blockedOn = null, Jc || (Jc = !0, i.unstable_scheduleCallback(
      i.unstable_NormalPriority,
      $S
    )));
  }
  var ju = null;
  function Gp(t) {
    ju !== t && (ju = t, i.unstable_scheduleCallback(
      i.unstable_NormalPriority,
      function() {
        ju === t && (ju = null);
        for (var e = 0; e < t.length; e += 3) {
          var n = t[e], a = t[e + 1], s = t[e + 2];
          if (typeof a != "function") {
            if (Kc(a || n) === null)
              continue;
            break;
          }
          var u = ei(n);
          u !== null && (t.splice(e, 3), e -= 3, Or(
            u,
            {
              pending: !0,
              data: s,
              method: n.method,
              action: a
            },
            a,
            s
          ));
        }
      }
    ));
  }
  function Gi(t) {
    function e(S) {
      return Vu(S, t);
    }
    fa !== null && Vu(fa, t), ha !== null && Vu(ha, t), da !== null && Vu(da, t), Xl.forEach(e), Ql.forEach(e);
    for (var n = 0; n < ma.length; n++) {
      var a = ma[n];
      a.blockedOn === t && (a.blockedOn = null);
    }
    for (; 0 < ma.length && (n = ma[0], n.blockedOn === null); )
      Yp(n), n.blockedOn === null && ma.shift();
    if (n = (t.ownerDocument || t).$$reactFormReplay, n != null)
      for (a = 0; a < n.length; a += 3) {
        var s = n[a], u = n[a + 1], f = s[Te] || null;
        if (typeof u == "function")
          f || Gp(n);
        else if (f) {
          var m = null;
          if (u && u.hasAttribute("formAction")) {
            if (s = u, f = u[Te] || null)
              m = f.formAction;
            else if (Kc(s) !== null) continue;
          } else m = f.action;
          typeof m == "function" ? n[a + 1] = m : (n.splice(a, 3), a -= 3), Gp(n);
        }
      }
  }
  function Xp() {
    function t(u) {
      u.canIntercept && u.info === "react-transition" && u.intercept({
        handler: function() {
          return new Promise(function(f) {
            return s = f;
          });
        },
        focusReset: "manual",
        scroll: "manual"
      });
    }
    function e() {
      s !== null && (s(), s = null), a || setTimeout(n, 20);
    }
    function n() {
      if (!a && !navigation.transition) {
        var u = navigation.currentEntry;
        u && u.url != null && navigation.navigate(u.url, {
          state: u.getState(),
          info: "react-transition",
          history: "replace"
        });
      }
    }
    if (typeof navigation == "object") {
      var a = !1, s = null;
      return navigation.addEventListener("navigate", t), navigation.addEventListener("navigatesuccess", e), navigation.addEventListener("navigateerror", e), setTimeout(n, 100), function() {
        a = !0, navigation.removeEventListener("navigate", t), navigation.removeEventListener("navigatesuccess", e), navigation.removeEventListener("navigateerror", e), s !== null && (s(), s = null);
      };
    }
  }
  function kc(t) {
    this._internalRoot = t;
  }
  Uu.prototype.render = kc.prototype.render = function(t) {
    var e = this._internalRoot;
    if (e === null) throw Error(o(409));
    var n = e.current, a = Ue();
    Vp(n, a, t, e, null, null);
  }, Uu.prototype.unmount = kc.prototype.unmount = function() {
    var t = this._internalRoot;
    if (t !== null) {
      this._internalRoot = null;
      var e = t.containerInfo;
      Vp(t.current, 2, null, t, null, null), Su(), e[ti] = null;
    }
  };
  function Uu(t) {
    this._internalRoot = t;
  }
  Uu.prototype.unstable_scheduleHydration = function(t) {
    if (t) {
      var e = Rh();
      t = { blockedOn: null, target: t, priority: e };
      for (var n = 0; n < ma.length && e !== 0 && e < ma[n].priority; n++) ;
      ma.splice(n, 0, t), n === 0 && Yp(t);
    }
  };
  var Qp = l.version;
  if (Qp !== "19.3.1")
    throw Error(
      o(
        527,
        Qp,
        "19.3.1"
      )
    );
  lt.findDOMNode = function(t) {
    var e = t._reactInternals;
    if (e === void 0)
      throw typeof t.render == "function" ? Error(o(188)) : (t = Object.keys(t).join(","), Error(o(268, t)));
    return t = b(e), t = t !== null ? g(t) : null, t = t === null ? null : t.stateNode, t;
  };
  var tT = {
    bundleType: 0,
    version: "19.3.1",
    rendererPackageName: "react-dom",
    currentDispatcherRef: W,
    reconcilerVersion: "19.3.1"
  };
  if (typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u") {
    var Bu = __REACT_DEVTOOLS_GLOBAL_HOOK__;
    if (!Bu.isDisabled && Bu.supportsFiber)
      try {
        $i = Bu.inject(
          tT
        ), Oe = Bu;
      } catch {
      }
  }
  return Jl.createRoot = function(t, e) {
    if (!c(t)) throw Error(o(299));
    var n = !1, a = "", s = wm, u = Vm, f = jm;
    return e != null && (e.unstable_strictMode === !0 && (n = !0), e.identifierPrefix !== void 0 && (a = e.identifierPrefix), e.onUncaughtError !== void 0 && (s = e.onUncaughtError), e.onCaughtError !== void 0 && (u = e.onCaughtError), e.onRecoverableError !== void 0 && (f = e.onRecoverableError)), e = _p(
      t,
      1,
      !1,
      null,
      null,
      n,
      a,
      null,
      s,
      u,
      f,
      Xp
    ), t[ti] = e.current, Ac(t), new kc(e);
  }, Jl.hydrateRoot = function(t, e, n) {
    if (!c(t)) throw Error(o(299));
    var a = !1, s = "", u = wm, f = Vm, m = jm, S = null;
    return n != null && (n.unstable_strictMode === !0 && (a = !0), n.identifierPrefix !== void 0 && (s = n.identifierPrefix), n.onUncaughtError !== void 0 && (u = n.onUncaughtError), n.onCaughtError !== void 0 && (f = n.onCaughtError), n.onRecoverableError !== void 0 && (m = n.onRecoverableError), n.formState !== void 0 && (S = n.formState)), e = _p(
      t,
      1,
      !0,
      e,
      n ?? null,
      a,
      s,
      S,
      u,
      f,
      m,
      Xp
    ), e.context = wp(null), n = e.current, a = Ue(), a = Eo(a), s = In(a), s.callback = null, $n(n, s, a), n = a, e.current.lanes = n, el(e, n), bn(e), t[ti] = e.current, Ac(t), new Uu(e);
  }, Jl.version = "19.3.1", Jl;
}
var t0;
function hT() {
  if (t0) return Wc.exports;
  t0 = 1;
  function i() {
    if (!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" || typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function"))
      try {
        __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(i);
      } catch (l) {
        console.error(l);
      }
  }
  return i(), Wc.exports = fT(), Wc.exports;
}
var dT = hT();
const Sg = K.createContext({});
function mT(i) {
  const l = K.useRef(null);
  return l.current === null && (l.current = i()), l.current;
}
const yT = typeof window < "u", pT = yT ? K.useLayoutEffect : K.useEffect, kf = /* @__PURE__ */ K.createContext(null);
function Pf(i, l) {
  i.indexOf(l) === -1 && i.push(l);
}
function Fu(i, l) {
  const r = i.indexOf(l);
  r > -1 && i.splice(r, 1);
}
const En = (i, l, r) => r > l ? l : r < i ? i : r;
let oo = () => {
};
const ga = {}, Tg = (i) => /^-?(?:\d+(?:\.\d+)?|\.\d+)$/u.test(i), xg = (i) => typeof i == "object" && i !== null, Eg = (i) => /^0[^.\s]+$/u.test(i);
// @__NO_SIDE_EFFECTS__
function Ag(i) {
  let l;
  return () => (l === void 0 && (l = i()), l);
}
const Pe = /* @__NO_SIDE_EFFECTS__ */ (i) => i, is = (...i) => i.reduce((l, r) => (o) => r(l(o))), ts = /* @__NO_SIDE_EFFECTS__ */ (i, l, r) => {
  const o = l - i;
  return o ? (r - i) / o : 1;
};
class Ff {
  constructor() {
    this.subscriptions = [];
  }
  add(l) {
    return Pf(this.subscriptions, l), () => Fu(this.subscriptions, l);
  }
  notify(l, r, o) {
    const c = this.subscriptions.length;
    if (c)
      if (c === 1)
        this.subscriptions[0](l, r, o);
      else
        for (let d = 0; d < c; d++) {
          const h = this.subscriptions[d];
          h && h(l, r, o);
        }
  }
  getSize() {
    return this.subscriptions.length;
  }
  clear() {
    this.subscriptions.length = 0;
  }
}
const He = /* @__NO_SIDE_EFFECTS__ */ (i) => i * 1e3, ke = /* @__NO_SIDE_EFFECTS__ */ (i) => i / 1e3, Mg = /* @__NO_SIDE_EFFECTS__ */ (i, l) => l ? i * (1e3 / l) : 0, Dg = (i, l, r) => (((1 - 3 * r + 3 * l) * i + (3 * r - 6 * l)) * i + 3 * l) * i, gT = 1e-7, vT = 12;
function bT(i, l, r, o, c) {
  let d, h, y = 0;
  do
    h = l + (r - l) / 2, d = Dg(h, o, c) - i, d > 0 ? r = h : l = h;
  while (Math.abs(d) > gT && ++y < vT);
  return h;
}
// @__NO_SIDE_EFFECTS__
function ls(i, l, r, o) {
  if (i === l && r === o)
    return Pe;
  const c = (d) => bT(d, 0, 1, i, r);
  return (d) => d === 0 || d === 1 ? d : Dg(c(d), l, o);
}
const Cg = /* @__NO_SIDE_EFFECTS__ */ (i) => (l) => l <= 0.5 ? i(2 * l) / 2 : (2 - i(2 * (1 - l))) / 2, Og = /* @__NO_SIDE_EFFECTS__ */ (i) => (l) => 1 - i(1 - l), Ng = /* @__PURE__ */ ls(0.33, 1.53, 0.69, 0.99), Wf = /* @__PURE__ */ Og(Ng), zg = /* @__PURE__ */ Cg(Wf), Rg = (i) => i >= 1 ? 1 : (i *= 2) < 1 ? 0.5 * Wf(i) : 0.5 * (2 - Math.pow(2, -10 * (i - 1))), If = (i) => 1 - Math.sin(Math.acos(i)), _g = /* @__PURE__ */ Og(If), wg = /* @__PURE__ */ Cg(If), ST = /* @__PURE__ */ ls(0.42, 0, 1, 1), TT = /* @__PURE__ */ ls(0, 0, 0.58, 1), Vg = /* @__PURE__ */ ls(0.42, 0, 0.58, 1), xT = /* @__NO_SIDE_EFFECTS__ */ (i) => Array.isArray(i) && typeof i[0] != "number", jg = /* @__NO_SIDE_EFFECTS__ */ (i) => Array.isArray(i) && typeof i[0] == "number", ET = {
  linear: Pe,
  easeIn: ST,
  easeInOut: Vg,
  easeOut: TT,
  circIn: If,
  circInOut: wg,
  circOut: _g,
  backIn: Wf,
  backInOut: zg,
  backOut: Ng,
  anticipate: Rg
}, AT = (i) => typeof i == "string", e0 = (i) => {
  if (/* @__PURE__ */ jg(i)) {
    oo(i.length === 4);
    const [l, r, o, c] = i;
    return /* @__PURE__ */ ls(l, r, o, c);
  } else if (AT(i))
    return ET[i];
  return i;
}, Hu = [
  "setup",
  // Compute
  "read",
  // Read
  "resolveKeyframes",
  // Write/Read/Write/Read
  "preUpdate",
  // Compute
  "update",
  // Compute
  "preRender",
  // Compute
  "render",
  // Write
  "postRender"
  // Compute
];
function MT(i) {
  let l = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), o = !1, c = !1;
  const d = /* @__PURE__ */ new WeakSet();
  let h = {
    delta: 0,
    timestamp: 0,
    isProcessing: !1
  };
  function y(b) {
    d.has(b) && (v.schedule(b), i()), b(h);
  }
  const v = {
    /**
     * Schedule a process to run on the next frame.
     */
    schedule: (b, g = !1, p = !1) => {
      const V = p && o ? l : r;
      return g && d.add(b), V.add(b), b;
    },
    /**
     * Cancel the provided callback from running on the next frame.
     */
    cancel: (b) => {
      r.delete(b), d.delete(b);
    },
    /**
     * Execute all schedule callbacks.
     */
    process: (b) => {
      if (h = b, o) {
        c = !0;
        return;
      }
      o = !0;
      const g = l;
      l = r, r = g, l.forEach(y), l.clear(), o = !1, c && (c = !1, v.process(b));
    }
  };
  return v;
}
const DT = 40;
function Ug(i, l) {
  let r = !1, o = !0;
  const c = {
    delta: 0,
    timestamp: 0,
    isProcessing: !1
  }, d = () => r = !0, h = Hu.reduce((U, G) => (U[G] = MT(d), U), {}), { setup: y, read: v, resolveKeyframes: b, preUpdate: g, update: p, preRender: T, render: V, postRender: z } = h, B = () => {
    const U = ga.useManualTiming, G = U ? c.timestamp : performance.now();
    r = !1, U || (c.delta = o ? 1e3 / 60 : Math.max(Math.min(G - c.timestamp, DT), 1)), c.timestamp = G, c.isProcessing = !0, y.process(c), v.process(c), b.process(c), g.process(c), p.process(c), T.process(c), V.process(c), z.process(c), c.isProcessing = !1, r && l && (o = !1, i(B));
  }, j = () => {
    r = !0, o = !0, c.isProcessing || i(B);
  };
  return { schedule: Hu.reduce((U, G) => {
    const nt = h[G];
    return U[G] = (rt, J = !1, Q = !1) => (r || j(), nt.schedule(rt, J, Q)), U;
  }, {}), cancel: (U) => {
    for (let G = 0; G < Hu.length; G++)
      h[Hu[G]].cancel(U);
  }, state: c, steps: h };
}
const { schedule: Vt, cancel: va, state: fe, steps: ef } = /* @__PURE__ */ Ug(typeof requestAnimationFrame < "u" ? requestAnimationFrame : Pe, !0);
let Gu;
function CT() {
  Gu = void 0;
}
const be = {
  now: () => (Gu === void 0 && be.set(fe.isProcessing || ga.useManualTiming ? fe.timestamp : performance.now()), Gu),
  set: (i) => {
    Gu = i, queueMicrotask(CT);
  }
}, Bg = (i) => (l) => typeof l == "string" && l.startsWith(i), Hg = /* @__PURE__ */ Bg("--"), OT = /* @__PURE__ */ Bg("var(--"), $f = (i) => OT(i) ? NT.test(i.split("/*")[0].trim()) : !1, NT = /var\(--(?:[\w-]+\s*|[\w-]+\s*,(?:\s*[^)(\s]|\s*\((?:[^)(]|\([^)(]*\))*\))+\s*)\)$/iu;
function n0(i) {
  return typeof i != "string" ? !1 : i.split("/*")[0].includes("var(--");
}
const Pi = {
  test: (i) => typeof i == "number",
  parse: parseFloat,
  transform: (i) => i
}, es = {
  ...Pi,
  transform: (i) => En(0, 1, i)
}, Lu = {
  ...Pi,
  default: 1
}, Fl = (i) => Math.round(i * 1e5) / 1e5, th = /-?(?:\d+(?:\.\d+)?|\.\d+)/gu;
function zT(i) {
  return i == null;
}
const RT = /^(?:#[\da-f]{3,8}|(?:rgb|hsl)a?\((?:-?[\d.]+%?[,\s]+){2}-?[\d.]+%?\s*(?:[,/]\s*)?(?:\b\d+(?:\.\d+)?|\.\d+)?%?\))$/iu, eh = (i, l) => (r) => !!(typeof r == "string" && RT.test(r) && r.startsWith(i) || l && !zT(r) && Object.prototype.hasOwnProperty.call(r, l)), Lg = (i, l, r) => (o) => {
  if (typeof o != "string")
    return o;
  const [c, d, h, y] = o.match(th);
  return {
    [i]: parseFloat(c),
    [l]: parseFloat(d),
    [r]: parseFloat(h),
    alpha: y !== void 0 ? parseFloat(y) : 1
  };
}, _T = (i) => En(0, 255, i), nf = {
  ...Pi,
  transform: (i) => Math.round(_T(i))
}, ka = {
  test: /* @__PURE__ */ eh("rgb", "red"),
  parse: /* @__PURE__ */ Lg("red", "green", "blue"),
  transform: ({ red: i, green: l, blue: r, alpha: o = 1 }) => "rgba(" + nf.transform(i) + ", " + nf.transform(l) + ", " + nf.transform(r) + ", " + Fl(es.transform(o)) + ")"
};
function wT(i) {
  let l = "", r = "", o = "", c = "";
  return i.length > 5 ? (l = i.substring(1, 3), r = i.substring(3, 5), o = i.substring(5, 7), c = i.substring(7, 9)) : (l = i.substring(1, 2), r = i.substring(2, 3), o = i.substring(3, 4), c = i.substring(4, 5), l += l, r += r, o += o, c += c), {
    red: parseInt(l, 16),
    green: parseInt(r, 16),
    blue: parseInt(o, 16),
    alpha: c ? parseInt(c, 16) / 255 : 1
  };
}
const Sf = {
  test: /* @__PURE__ */ eh("#"),
  parse: wT,
  transform: ka.transform
}, ss = /* @__NO_SIDE_EFFECTS__ */ (i) => ({
  test: (l) => typeof l == "string" && l.endsWith(i) && l.split(" ").length === 1,
  parse: parseFloat,
  transform: (l) => `${l}${i}`
}), Yn = /* @__PURE__ */ ss("deg"), xn = /* @__PURE__ */ ss("%"), F = /* @__PURE__ */ ss("px"), VT = /* @__PURE__ */ ss("vh"), jT = /* @__PURE__ */ ss("vw"), a0 = {
  ...xn,
  parse: (i) => xn.parse(i) / 100,
  transform: (i) => xn.transform(i * 100)
}, Qi = {
  test: /* @__PURE__ */ eh("hsl", "hue"),
  parse: /* @__PURE__ */ Lg("hue", "saturation", "lightness"),
  transform: ({ hue: i, saturation: l, lightness: r, alpha: o = 1 }) => "hsla(" + Math.round(i) + ", " + xn.transform(Fl(l)) + ", " + xn.transform(Fl(r)) + ", " + Fl(es.transform(o)) + ")"
}, kt = {
  test: (i) => ka.test(i) || Sf.test(i) || Qi.test(i),
  parse: (i) => ka.test(i) ? ka.parse(i) : Qi.test(i) ? Qi.parse(i) : Sf.parse(i),
  transform: (i) => typeof i == "string" ? i : i.hasOwnProperty("red") ? ka.transform(i) : Qi.transform(i),
  getAnimatableNone: (i) => {
    const l = kt.parse(i);
    return l.alpha = 0, kt.transform(l);
  }
}, UT = /(?:#[\da-f]{3,8}|(?:rgb|hsl)a?\((?:-?[\d.]+%?[,\s]+){2}-?[\d.]+%?\s*(?:[,/]\s*)?(?:\b\d+(?:\.\d+)?|\.\d+)?%?\))/giu;
function BT(i) {
  return isNaN(i) && typeof i == "string" && (i.match(th)?.length || 0) + (i.match(UT)?.length || 0) > 0;
}
const Yg = "number", qg = "color", HT = "var", LT = "var(", i0 = "${}", YT = /var\s*\(\s*--(?:[\w-]+\s*|[\w-]+\s*,(?:\s*[^)(\s]|\s*\((?:[^)(]|\([^)(]*\))*\))+\s*)\)|#[\da-f]{3,8}|(?:rgb|hsl)a?\((?:-?[\d.]+%?[,\s]+){2}-?[\d.]+%?\s*(?:[,/]\s*)?(?:\b\d+(?:\.\d+)?|\.\d+)?%?\)|-?(?:\d+(?:\.\d+)?|\.\d+)/giu;
function Ji(i) {
  const l = i.toString(), r = [], o = {
    color: [],
    number: [],
    var: []
  }, c = [];
  let d = 0;
  const y = l.replace(YT, (v) => (kt.test(v) ? (o.color.push(d), c.push(qg), r.push(kt.parse(v))) : v.startsWith(LT) ? (o.var.push(d), c.push(HT), r.push(v)) : (o.number.push(d), c.push(Yg), r.push(parseFloat(v))), ++d, i0)).split(i0);
  return { values: r, split: y, indexes: o, types: c };
}
function qT(i) {
  return Ji(i).values;
}
function Gg({ split: i, types: l }) {
  const r = i.length;
  return (o) => {
    let c = "";
    for (let d = 0; d < r; d++)
      if (c += i[d], o[d] !== void 0) {
        const h = l[d];
        h === Yg ? c += Fl(o[d]) : h === qg ? c += kt.transform(o[d]) : c += o[d];
      }
    return c;
  };
}
function GT(i) {
  return Gg(Ji(i));
}
const XT = (i) => typeof i == "number" ? 0 : kt.test(i) ? kt.getAnimatableNone(i) : i, QT = (i, l) => typeof i == "number" ? l?.trim().endsWith("/") ? i : 0 : XT(i);
function ZT(i) {
  const l = Ji(i);
  return Gg(l)(l.values.map((o, c) => QT(o, l.split[c])));
}
const sn = {
  test: BT,
  parse: qT,
  createTransformer: GT,
  getAnimatableNone: ZT
};
function af(i, l, r) {
  return r < 0 && (r += 1), r > 1 && (r -= 1), r < 1 / 6 ? i + (l - i) * 6 * r : r < 1 / 2 ? l : r < 2 / 3 ? i + (l - i) * (2 / 3 - r) * 6 : i;
}
function KT({ hue: i, saturation: l, lightness: r, alpha: o }) {
  i /= 360, l /= 100, r /= 100;
  let c = 0, d = 0, h = 0;
  if (!l)
    c = d = h = r;
  else {
    const y = r < 0.5 ? r * (1 + l) : r + l - r * l, v = 2 * r - y;
    c = af(v, y, i + 1 / 3), d = af(v, y, i), h = af(v, y, i - 1 / 3);
  }
  return {
    red: Math.round(c * 255),
    green: Math.round(d * 255),
    blue: Math.round(h * 255),
    alpha: o
  };
}
function Wu(i, l) {
  return (r) => r > 0 ? l : i;
}
const wt = (i, l, r) => i + (l - i) * r, lf = (i, l, r) => {
  const o = i * i, c = r * (l * l - o) + o;
  return c < 0 ? 0 : Math.sqrt(c);
}, JT = [Sf, ka, Qi], kT = (i) => JT.find((l) => l.test(i));
function l0(i) {
  const l = kT(i);
  if (!l)
    return !1;
  let r = l.parse(i);
  return l === Qi && (r = KT(r)), r;
}
const s0 = (i, l) => {
  const r = l0(i), o = l0(l);
  if (!r || !o)
    return Wu(i, l);
  const c = { ...r };
  return (d) => (c.red = lf(r.red, o.red, d), c.green = lf(r.green, o.green, d), c.blue = lf(r.blue, o.blue, d), c.alpha = wt(r.alpha, o.alpha, d), ka.transform(c));
}, Tf = /* @__PURE__ */ new Set(["none", "hidden"]);
function PT(i, l) {
  return Tf.has(i) ? (r) => r <= 0 ? i : l : (r) => r >= 1 ? l : i;
}
function FT(i, l) {
  return (r) => wt(i, l, r);
}
function nh(i) {
  return typeof i == "number" ? FT : typeof i == "string" ? $f(i) ? Wu : kt.test(i) ? s0 : $T : Array.isArray(i) ? Xg : typeof i == "object" ? kt.test(i) ? s0 : WT : Wu;
}
function Xg(i, l) {
  const r = [...i], o = r.length, c = i.map((d, h) => nh(d)(d, l[h]));
  return (d) => {
    for (let h = 0; h < o; h++)
      r[h] = c[h](d);
    return r;
  };
}
function WT(i, l) {
  const r = { ...i, ...l }, o = {};
  for (const c in r)
    i[c] !== void 0 && l[c] !== void 0 && (o[c] = nh(i[c])(i[c], l[c]));
  return (c) => {
    for (const d in o)
      r[d] = o[d](c);
    return r;
  };
}
function IT(i, l) {
  const r = [], o = { color: 0, var: 0, number: 0 };
  for (let c = 0; c < l.values.length; c++) {
    const d = l.types[c], h = i.indexes[d][o[d]], y = i.values[h] ?? 0;
    r[c] = y, o[d]++;
  }
  return r;
}
const $T = (i, l) => {
  const r = sn.createTransformer(l), o = Ji(i), c = Ji(l);
  return o.indexes.var.length === c.indexes.var.length && o.indexes.color.length === c.indexes.color.length && o.indexes.number.length >= c.indexes.number.length ? Tf.has(i) && !c.values.length || Tf.has(l) && !o.values.length ? PT(i, l) : is(Xg(IT(o, c), c.values), r) : Wu(i, l);
};
function Qg(i, l, r) {
  return typeof i == "number" && typeof l == "number" && typeof r == "number" ? wt(i, l, r) : nh(i)(i, l);
}
const tx = (i) => {
  const l = ({ timestamp: r }) => i(r);
  return {
    start: (r = !0) => Vt.update(l, r),
    stop: () => va(l),
    /**
     * If we're processing this frame we can use the
     * framelocked timestamp to keep things in sync.
     */
    now: () => fe.isProcessing ? fe.timestamp : be.now()
  };
}, Zg = (i, l, r = 10) => {
  let o = "";
  const c = Math.max(Math.round(l / r), 2);
  for (let d = 0; d < c; d++)
    o += Math.round(i(d / (c - 1)) * 1e4) / 1e4 + ", ";
  return `linear(${o.substring(0, o.length - 2)})`;
}, Iu = 2e4;
function ah(i) {
  let l = 0;
  const r = 50;
  let o = i.next(l);
  for (; !o.done && l < Iu; )
    l += r, o = i.next(l);
  return l >= Iu ? 1 / 0 : l;
}
function ex(i, l = 100, r) {
  const o = r({ ...i, keyframes: [0, l] }), c = Math.min(ah(o), Iu);
  return {
    type: "keyframes",
    ease: (d) => o.next(c * d).value / l,
    duration: /* @__PURE__ */ ke(c)
  };
}
const Gt = {
  // Default spring physics
  stiffness: 100,
  damping: 10,
  mass: 1,
  velocity: 0,
  // Default duration/bounce-based options
  duration: 800,
  // in ms
  bounce: 0.3,
  visualDuration: 0.3,
  // in seconds
  // Rest thresholds
  restSpeed: {
    granular: 0.01,
    default: 2
  },
  restDelta: {
    granular: 5e-3,
    default: 0.5
  },
  // Limits
  minDuration: 0.01,
  // in seconds
  maxDuration: 10,
  // in seconds
  minDamping: 0.05,
  maxDamping: 1
};
function xf(i, l) {
  return i * Math.sqrt(1 - l * l);
}
const nx = 12;
function ax(i, l, r) {
  let o = r;
  for (let c = 1; c < nx; c++)
    o = o - i(o) / l(o);
  return o;
}
const sf = 1e-3;
function ix({ duration: i = Gt.duration, bounce: l = Gt.bounce, velocity: r = Gt.velocity, mass: o = Gt.mass }) {
  let c, d, h = 1 - l;
  h = En(Gt.minDamping, Gt.maxDamping, h), i = En(Gt.minDuration, Gt.maxDuration, /* @__PURE__ */ ke(i)), h < 1 ? (c = (b) => {
    const g = b * h, p = g * i, T = g - r, V = xf(b, h), z = Math.exp(-p);
    return sf - T / V * z;
  }, d = (b) => {
    const p = b * h * i, T = p * r + r, V = Math.pow(h, 2) * Math.pow(b, 2) * i, z = Math.exp(-p), B = xf(Math.pow(b, 2), h);
    return (-c(b) + sf > 0 ? -1 : 1) * ((T - V) * z) / B;
  }) : (c = (b) => {
    const g = Math.exp(-b * i), p = (b - r) * i + 1;
    return -sf + g * p;
  }, d = (b) => {
    const g = Math.exp(-b * i), p = (r - b) * (i * i);
    return g * p;
  });
  const y = 5 / i, v = ax(c, d, y);
  if (i = /* @__PURE__ */ He(i), isNaN(v))
    return {
      stiffness: Gt.stiffness,
      damping: Gt.damping,
      duration: i
    };
  {
    const b = Math.pow(v, 2) * o;
    return {
      stiffness: b,
      damping: h * 2 * Math.sqrt(o * b),
      duration: i
    };
  }
}
const lx = ["duration", "bounce"], sx = ["stiffness", "damping", "mass"];
function u0(i, l) {
  return l.some((r) => i[r] !== void 0);
}
function ux(i) {
  let l = {
    velocity: Gt.velocity,
    stiffness: Gt.stiffness,
    damping: Gt.damping,
    mass: Gt.mass,
    isResolvedFromDuration: !1,
    ...i
  };
  if (!u0(i, sx) && u0(i, lx))
    if (l.velocity = 0, i.visualDuration) {
      const r = i.visualDuration, o = 2 * Math.PI / (r * 1.2), c = o * o, d = 2 * En(0.05, 1, 1 - (i.bounce || 0)) * Math.sqrt(c);
      l = {
        ...l,
        mass: Gt.mass,
        stiffness: c,
        damping: d
      };
    } else {
      const r = ix({ ...i, velocity: 0 });
      l = {
        ...l,
        ...r,
        mass: Gt.mass
      }, l.isResolvedFromDuration = !0;
    }
  return l;
}
function $u(i = Gt.visualDuration, l = Gt.bounce) {
  const r = typeof i != "object" ? {
    visualDuration: i,
    keyframes: [0, 1],
    bounce: l
  } : i;
  let { restSpeed: o, restDelta: c } = r;
  const d = r.keyframes[0], h = r.keyframes[r.keyframes.length - 1], y = { done: !1, value: d }, { stiffness: v, damping: b, mass: g, duration: p, velocity: T, isResolvedFromDuration: V } = ux({
    ...r,
    velocity: -/* @__PURE__ */ ke(r.velocity || 0)
  }), z = T || 0, B = b / (2 * Math.sqrt(v * g)), j = h - d, L = /* @__PURE__ */ ke(Math.sqrt(v / g)), Y = Math.abs(j) < 5;
  o || (o = Y ? Gt.restSpeed.granular : Gt.restSpeed.default), c || (c = Y ? Gt.restDelta.granular : Gt.restDelta.default);
  let U, G, nt, rt, J, Q;
  if (B < 1)
    nt = xf(L, B), rt = (z + B * L * j) / nt, U = ($) => {
      const vt = Math.exp(-B * L * $);
      return h - vt * (rt * Math.sin(nt * $) + j * Math.cos(nt * $));
    }, J = B * L * rt + j * nt, Q = B * L * j - rt * nt, G = ($) => Math.exp(-B * L * $) * (J * Math.sin(nt * $) + Q * Math.cos(nt * $));
  else if (B === 1) {
    U = (vt) => h - Math.exp(-L * vt) * (j + (z + L * j) * vt);
    const $ = z + L * j;
    G = (vt) => Math.exp(-L * vt) * (L * $ * vt - z);
  } else {
    const $ = L * Math.sqrt(B * B - 1);
    U = (Wt) => {
      const zt = Math.exp(-B * L * Wt), q = Math.min($ * Wt, 300);
      return h - zt * ((z + B * L * j) * Math.sinh(q) + $ * j * Math.cosh(q)) / $;
    };
    const vt = (z + B * L * j) / $, Nt = B * L * vt - j * $, de = B * L * j - vt * $;
    G = (Wt) => {
      const zt = Math.exp(-B * L * Wt), q = Math.min($ * Wt, 300);
      return zt * (Nt * Math.sinh(q) + de * Math.cosh(q));
    };
  }
  const Ot = {
    calculatedDuration: V && p || null,
    velocity: ($) => /* @__PURE__ */ He(G($)),
    next: ($) => {
      if (!V && B < 1) {
        const Nt = Math.exp(-B * L * $), de = Math.sin(nt * $), Wt = Math.cos(nt * $), zt = h - Nt * (rt * de + j * Wt), q = /* @__PURE__ */ He(Nt * (J * de + Q * Wt));
        return y.done = Math.abs(q) <= o && Math.abs(h - zt) <= c, y.value = y.done ? h : zt, y;
      }
      const vt = U($);
      if (V)
        y.done = $ >= p;
      else {
        const Nt = /* @__PURE__ */ He(G($));
        y.done = Math.abs(Nt) <= o && Math.abs(h - vt) <= c;
      }
      return y.value = y.done ? h : vt, y;
    },
    toString: () => {
      const $ = Math.min(ah(Ot), Iu), vt = Zg((Nt) => Ot.next($ * Nt).value, $, 30);
      return $ + "ms " + vt;
    },
    toTransition: () => {
    }
  };
  return Ot;
}
$u.applyToOptions = (i) => {
  const l = ex(i, 100, $u);
  return i.ease = l.ease, i.duration = /* @__PURE__ */ He(l.duration), i.type = "keyframes", i;
};
const ox = 5;
function Kg(i, l, r) {
  const o = Math.max(l - ox, 0);
  return /* @__PURE__ */ Mg(r - i(o), l - o);
}
function Ef({ keyframes: i, velocity: l = 0, power: r = 0.8, timeConstant: o = 325, bounceDamping: c = 10, bounceStiffness: d = 500, modifyTarget: h, min: y, max: v, restDelta: b = 0.5, restSpeed: g }) {
  const p = i[0], T = {
    done: !1,
    value: p
  }, V = (Q) => y !== void 0 && Q < y || v !== void 0 && Q > v, z = (Q) => y === void 0 ? v : v === void 0 || Math.abs(y - Q) < Math.abs(v - Q) ? y : v;
  let B = r * l;
  const j = p + B, L = h === void 0 ? j : h(j);
  L !== j && (B = L - p);
  const Y = (Q) => -B * Math.exp(-Q / o), U = (Q) => L + Y(Q), G = (Q) => {
    const Ot = Y(Q), $ = U(Q);
    T.done = Math.abs(Ot) <= b, T.value = T.done ? L : $;
  };
  let nt, rt;
  const J = (Q) => {
    V(T.value) && (nt = Q, rt = $u({
      keyframes: [T.value, z(T.value)],
      velocity: Kg(U, Q, T.value),
      // TODO: This should be passing * 1000
      damping: c,
      stiffness: d,
      restDelta: b,
      restSpeed: g
    }));
  };
  return J(0), {
    calculatedDuration: null,
    next: (Q) => {
      let Ot = !1;
      return !rt && nt === void 0 && (Ot = !0, G(Q), J(Q)), nt !== void 0 && Q >= nt ? rt.next(Q - nt) : (!Ot && G(Q), T);
    }
  };
}
function rx(i, l, r) {
  const o = [], c = r || ga.mix || Qg, d = i.length - 1;
  for (let h = 0; h < d; h++) {
    let y = c(i[h], i[h + 1]);
    if (l) {
      const v = Array.isArray(l) ? l[h] || Pe : l;
      y = is(v, y);
    }
    o.push(y);
  }
  return o;
}
function cx(i, l, { clamp: r = !0, ease: o, mixer: c } = {}) {
  const d = i.length;
  if (oo(d === l.length), d === 1)
    return () => l[0];
  if (d === 2 && l[0] === l[1])
    return () => l[1];
  const h = i[0] === i[1];
  i[0] > i[d - 1] && (i = [...i].reverse(), l = [...l].reverse());
  const y = rx(l, o, c), v = y.length, b = (g) => {
    if (h && g < i[0])
      return l[0];
    let p = 0;
    if (v > 1)
      for (; p < i.length - 2 && !(g < i[p + 1]); p++)
        ;
    const T = /* @__PURE__ */ ts(i[p], i[p + 1], g);
    return y[p](T);
  };
  return r ? (g) => b(En(i[0], i[d - 1], g)) : b;
}
function fx(i, l) {
  const r = i[i.length - 1];
  for (let o = 1; o <= l; o++) {
    const c = /* @__PURE__ */ ts(0, l, o);
    i.push(wt(r, 1, c));
  }
}
function hx(i) {
  const l = [0];
  return fx(l, i.length - 1), l;
}
function dx(i, l) {
  return i.map((r) => r * l);
}
function mx(i, l) {
  return i.map(() => l || Vg).splice(0, i.length - 1);
}
function Wl({ duration: i = 300, keyframes: l, times: r, ease: o = "easeInOut" }) {
  const c = /* @__PURE__ */ xT(o) ? o.map(e0) : e0(o), d = {
    done: !1,
    value: l[0]
  }, h = dx(
    // Only use the provided offsets if they're the correct length
    // TODO Maybe we should warn here if there's a length mismatch
    r && r.length === l.length ? r : hx(l),
    i
  ), y = cx(h, l, {
    ease: Array.isArray(c) ? c : mx(l, c)
  });
  return {
    calculatedDuration: i,
    next: (v) => (d.value = y(v), d.done = v >= i, d)
  };
}
const yx = (i) => i !== null;
function ro(i, { repeat: l, repeatType: r = "loop" }, o, c = 1) {
  const d = i.filter(yx), y = c < 0 || l && r !== "loop" && l % 2 === 1 ? 0 : d.length - 1;
  return !y || o === void 0 ? d[y] : o;
}
const px = {
  decay: Ef,
  inertia: Ef,
  tween: Wl,
  keyframes: Wl,
  spring: $u
};
function Jg(i) {
  typeof i.type == "string" && (i.type = px[i.type]);
}
class ih {
  constructor() {
    this.updateFinished();
  }
  get finished() {
    return this._finished;
  }
  updateFinished() {
    this._finished = new Promise((l) => {
      this.resolve = l;
    });
  }
  notifyFinished() {
    this.resolve();
  }
  /**
   * Allows the animation to be awaited.
   *
   * @deprecated Use `finished` instead.
   */
  then(l, r) {
    return this.finished.then(l, r);
  }
}
const gx = (i) => i / 100;
class to extends ih {
  constructor(l) {
    super(), this.state = "idle", this.startTime = null, this.isStopped = !1, this.currentTime = 0, this.holdTime = null, this.playbackSpeed = 1, this.delayState = {
      done: !1,
      value: void 0
    }, this.stop = () => {
      const { motionValue: r } = this.options;
      r && r.updatedAt !== be.now() && this.tick(be.now()), this.isStopped = !0, this.state !== "idle" && (this.teardown(), this.options.onStop?.());
    }, this.options = l, this.initAnimation(), this.play(), l.autoplay === !1 && this.pause();
  }
  initAnimation() {
    const { options: l } = this;
    Jg(l);
    const { type: r = Wl, repeat: o = 0, repeatDelay: c = 0, repeatType: d, velocity: h = 0 } = l;
    let { keyframes: y } = l;
    const v = r || Wl;
    v !== Wl && typeof y[0] != "number" && (this.mixKeyframes = is(gx, Qg(y[0], y[1])), y = [0, 100]);
    const b = v({ ...l, keyframes: y });
    d === "mirror" && (this.mirroredGenerator = v({
      ...l,
      keyframes: [...y].reverse(),
      velocity: -h
    })), b.calculatedDuration === null && (b.calculatedDuration = ah(b));
    const { calculatedDuration: g } = b;
    this.calculatedDuration = g, this.resolvedDuration = g + c, this.totalDuration = this.resolvedDuration * (o + 1) - c, this.generator = b;
  }
  updateTime(l) {
    const r = Math.round(l - this.startTime) * this.playbackSpeed;
    this.holdTime !== null ? this.currentTime = this.holdTime : this.currentTime = r;
  }
  tick(l, r = !1) {
    const { generator: o, totalDuration: c, mixKeyframes: d, mirroredGenerator: h, resolvedDuration: y, calculatedDuration: v } = this;
    if (this.startTime === null)
      return o.next(0);
    const { delay: b = 0, keyframes: g, repeat: p, repeatType: T, repeatDelay: V, type: z, onUpdate: B, finalKeyframe: j } = this.options;
    this.speed > 0 ? this.startTime = Math.min(this.startTime, l) : this.speed < 0 && (this.startTime = Math.min(l - c / this.speed, this.startTime)), r ? this.currentTime = l : this.updateTime(l);
    const L = this.currentTime - b * (this.playbackSpeed >= 0 ? 1 : -1), Y = this.playbackSpeed >= 0 ? L < 0 : L > c;
    this.currentTime = Math.max(L, 0), this.state === "finished" && this.holdTime === null && (this.currentTime = c);
    let U = this.currentTime, G = o;
    if (p) {
      const Q = Math.min(this.currentTime, c) / y;
      let Ot = Math.floor(Q), $ = Q % 1;
      !$ && Q >= 1 && ($ = 1), $ === 1 && Ot--, Ot = Math.min(Ot, p + 1), Ot % 2 && (T === "reverse" ? ($ = 1 - $, V && ($ -= V / y)) : T === "mirror" && (G = h)), U = En(0, 1, $) * y;
    }
    let nt;
    Y ? (this.delayState.value = g[0], nt = this.delayState) : nt = G.next(U), d && !Y && (nt.value = d(nt.value));
    let { done: rt } = nt;
    !Y && v !== null && (rt = this.playbackSpeed >= 0 ? this.currentTime >= c : this.currentTime <= 0);
    const J = this.holdTime === null && (this.state === "finished" || this.state === "running" && rt);
    return J && z !== Ef && (nt.value = ro(g, this.options, j, this.speed)), B && B(nt.value), J && this.finish(), nt;
  }
  /**
   * Allows the returned animation to be awaited or promise-chained. Currently
   * resolves when the animation finishes at all but in a future update could/should
   * reject if its cancels.
   */
  then(l, r) {
    return this.finished.then(l, r);
  }
  get duration() {
    return /* @__PURE__ */ ke(this.calculatedDuration);
  }
  get iterationDuration() {
    const { delay: l = 0 } = this.options || {};
    return this.duration + /* @__PURE__ */ ke(l);
  }
  get time() {
    return /* @__PURE__ */ ke(this.currentTime);
  }
  set time(l) {
    l = /* @__PURE__ */ He(l), this.currentTime = l, this.startTime === null || this.holdTime !== null || this.playbackSpeed === 0 ? this.holdTime = l : this.driver && (this.startTime = this.driver.now() - l / this.playbackSpeed), this.driver ? this.driver.start(!1) : (this.startTime = 0, this.state = "paused", this.holdTime = l, this.tick(l));
  }
  /**
   * Returns the generator's velocity at the current time in units/second.
   * Uses the analytical derivative when available (springs), avoiding
   * the MotionValue's frame-dependent velocity estimation.
   */
  getGeneratorVelocity() {
    const l = this.currentTime;
    if (l <= 0)
      return this.options.velocity || 0;
    if (this.generator.velocity)
      return this.generator.velocity(l);
    const r = this.generator.next(l).value;
    return Kg((o) => this.generator.next(o).value, l, r);
  }
  get speed() {
    return this.playbackSpeed;
  }
  set speed(l) {
    const r = this.playbackSpeed !== l;
    r && this.driver && this.updateTime(be.now()), this.playbackSpeed = l, r && this.driver && (this.time = /* @__PURE__ */ ke(this.currentTime));
  }
  play() {
    if (this.isStopped)
      return;
    const { driver: l = tx, startTime: r } = this.options;
    this.driver || (this.driver = l((c) => this.tick(c))), this.options.onPlay?.();
    const o = this.driver.now();
    this.state === "finished" ? (this.updateFinished(), this.startTime = o) : this.holdTime !== null ? this.startTime = o - this.holdTime : this.startTime || (this.startTime = r ?? o), this.state === "finished" && this.speed < 0 && (this.startTime += this.calculatedDuration), this.holdTime = null, this.state = "running", this.driver.start();
  }
  pause() {
    this.state = "paused", this.updateTime(be.now()), this.holdTime = this.currentTime;
  }
  complete() {
    this.state !== "running" && this.play(), this.state = "finished", this.holdTime = null;
  }
  finish() {
    this.notifyFinished(), this.teardown(), this.state = "finished", this.options.onComplete?.();
  }
  cancel() {
    this.holdTime = null, this.startTime = 0, this.tick(0), this.teardown(), this.options.onCancel?.();
  }
  teardown() {
    this.state = "idle", this.stopDriver(), this.startTime = this.holdTime = null;
  }
  stopDriver() {
    this.driver && (this.driver.stop(), this.driver = void 0);
  }
  sample(l) {
    return this.startTime = 0, this.tick(l, !0);
  }
  attachTimeline(l) {
    return this.options.allowFlatten && (this.options.type = "keyframes", this.options.ease = "linear", this.initAnimation()), this.driver?.stop(), l.observe(this);
  }
}
function vx(i) {
  for (let l = 1; l < i.length; l++)
    i[l] ?? (i[l] = i[l - 1]);
}
const Pa = (i) => i * 180 / Math.PI, Af = (i) => {
  const l = Pa(Math.atan2(i[1], i[0]));
  return Mf(l);
}, bx = {
  x: 4,
  y: 5,
  translateX: 4,
  translateY: 5,
  scaleX: 0,
  scaleY: 3,
  scale: (i) => (Math.abs(i[0]) + Math.abs(i[3])) / 2,
  rotate: Af,
  rotateZ: Af,
  skewX: (i) => Pa(Math.atan(i[1])),
  skewY: (i) => Pa(Math.atan(i[2])),
  skew: (i) => (Math.abs(i[1]) + Math.abs(i[2])) / 2
}, Mf = (i) => (i = i % 360, i < 0 && (i += 360), i), o0 = Af, r0 = (i) => Math.sqrt(i[0] * i[0] + i[1] * i[1]), c0 = (i) => Math.sqrt(i[4] * i[4] + i[5] * i[5]), Sx = {
  x: 12,
  y: 13,
  z: 14,
  translateX: 12,
  translateY: 13,
  translateZ: 14,
  scaleX: r0,
  scaleY: c0,
  scale: (i) => (r0(i) + c0(i)) / 2,
  rotateX: (i) => Mf(Pa(Math.atan2(i[6], i[5]))),
  rotateY: (i) => Mf(Pa(Math.atan2(-i[2], i[0]))),
  rotateZ: o0,
  rotate: o0,
  skewX: (i) => Pa(Math.atan(i[4])),
  skewY: (i) => Pa(Math.atan(i[1])),
  skew: (i) => (Math.abs(i[1]) + Math.abs(i[4])) / 2
};
function Df(i) {
  return i.includes("scale") ? 1 : 0;
}
function Cf(i, l) {
  if (!i || i === "none")
    return Df(l);
  const r = i.match(/^matrix3d\(([-\d.e\s,]+)\)$/u);
  let o, c;
  if (r)
    o = Sx, c = r;
  else {
    const y = i.match(/^matrix\(([-\d.e\s,]+)\)$/u);
    o = bx, c = y;
  }
  if (!c)
    return Df(l);
  const d = o[l], h = c[1].split(",").map(xx);
  return typeof d == "function" ? d(h) : h[d];
}
const Tx = (i, l) => {
  const { transform: r = "none" } = getComputedStyle(i);
  return Cf(r, l);
};
function xx(i) {
  return parseFloat(i.trim());
}
const Fi = [
  "transformPerspective",
  "x",
  "y",
  "z",
  "translateX",
  "translateY",
  "translateZ",
  "scale",
  "scaleX",
  "scaleY",
  "rotate",
  "rotateX",
  "rotateY",
  "rotateZ",
  "skew",
  "skewX",
  "skewY"
], Wi = /* @__PURE__ */ new Set([...Fi, "pathRotation"]), f0 = (i) => i === Pi || i === F, Ex = /* @__PURE__ */ new Set(["x", "y", "z"]), Ax = Fi.filter((i) => !Ex.has(i));
function Mx(i) {
  const l = [];
  return Ax.forEach((r) => {
    const o = i.getValue(r);
    o !== void 0 && (l.push([r, o.get()]), o.set(r.startsWith("scale") ? 1 : 0));
  }), l;
}
const pa = {
  // Dimensions
  width: ({ x: i }, { paddingLeft: l = "0", paddingRight: r = "0", boxSizing: o }) => {
    const c = i.max - i.min;
    return o === "border-box" ? c : c - parseFloat(l) - parseFloat(r);
  },
  height: ({ y: i }, { paddingTop: l = "0", paddingBottom: r = "0", boxSizing: o }) => {
    const c = i.max - i.min;
    return o === "border-box" ? c : c - parseFloat(l) - parseFloat(r);
  },
  top: (i, { top: l }) => parseFloat(l),
  left: (i, { left: l }) => parseFloat(l),
  bottom: ({ y: i }, { top: l }) => parseFloat(l) + (i.max - i.min),
  right: ({ x: i }, { left: l }) => parseFloat(l) + (i.max - i.min),
  // Transform
  x: (i, { transform: l }) => Cf(l, "x"),
  y: (i, { transform: l }) => Cf(l, "y")
};
pa.translateX = pa.x;
pa.translateY = pa.y;
const Fa = /* @__PURE__ */ new Set();
let Of = !1, Nf = !1, zf = !1;
function kg() {
  if (Nf) {
    const i = Array.from(Fa).filter((o) => o.needsMeasurement), l = new Set(i.map((o) => o.element)), r = /* @__PURE__ */ new Map();
    l.forEach((o) => {
      const c = Mx(o);
      c.length && (r.set(o, c), o.render());
    }), i.forEach((o) => o.measureInitialState()), l.forEach((o) => {
      o.render();
      const c = r.get(o);
      c && c.forEach(([d, h]) => {
        o.getValue(d)?.set(h);
      });
    }), i.forEach((o) => o.measureEndState()), i.forEach((o) => {
      o.suspendedScrollY !== void 0 && window.scrollTo(0, o.suspendedScrollY);
    });
  }
  Nf = !1, Of = !1, Fa.forEach((i) => i.complete(zf)), Fa.clear();
}
function Pg() {
  Fa.forEach((i) => {
    i.readKeyframes(), i.needsMeasurement && (Nf = !0);
  });
}
function Dx() {
  zf = !0, Pg(), kg(), zf = !1;
}
class lh {
  constructor(l, r, o, c, d, h = !1) {
    this.state = "pending", this.isAsync = !1, this.needsMeasurement = !1, this.unresolvedKeyframes = [...l], this.onComplete = r, this.name = o, this.motionValue = c, this.element = d, this.isAsync = h;
  }
  scheduleResolve() {
    this.state = "scheduled", this.isAsync ? (Fa.add(this), Of || (Of = !0, Vt.read(Pg), Vt.resolveKeyframes(kg))) : (this.readKeyframes(), this.complete());
  }
  readKeyframes() {
    const { unresolvedKeyframes: l, name: r, element: o, motionValue: c } = this;
    if (l[0] === null) {
      const d = c?.get(), h = l[l.length - 1];
      if (d !== void 0)
        l[0] = d;
      else if (o && r) {
        const y = o.readValue(r, h);
        y != null && (l[0] = y);
      }
      l[0] === void 0 && (l[0] = h), c && d === void 0 && c.set(l[0]);
    }
    vx(l);
  }
  setFinalKeyframe() {
  }
  measureInitialState() {
  }
  renderEndStyles() {
  }
  measureEndState() {
  }
  complete(l = !1) {
    this.state = "complete", this.onComplete(this.unresolvedKeyframes, this.finalKeyframe, l), Fa.delete(this);
  }
  cancel() {
    this.state === "scheduled" && (Fa.delete(this), this.state = "pending");
  }
  resume() {
    this.state === "pending" && this.scheduleResolve();
  }
}
const Cx = (i) => i.startsWith("--");
function Fg(i, l, r) {
  Cx(l) ? i.style.setProperty(l, r) : i.style[l] = r;
}
const Ox = {};
function Wg(i, l) {
  const r = /* @__PURE__ */ Ag(i);
  return () => Ox[l] ?? r();
}
const Nx = /* @__PURE__ */ Wg(() => window.ScrollTimeline !== void 0, "scrollTimeline"), Ig = /* @__PURE__ */ Wg(() => {
  try {
    document.createElement("div").animate({ opacity: 0 }, { easing: "linear(0, 1)" });
  } catch {
    return !1;
  }
  return !0;
}, "linearEasing"), Pl = ([i, l, r, o]) => `cubic-bezier(${i}, ${l}, ${r}, ${o})`, h0 = {
  linear: "linear",
  ease: "ease",
  easeIn: "ease-in",
  easeOut: "ease-out",
  easeInOut: "ease-in-out",
  circIn: /* @__PURE__ */ Pl([0, 0.65, 0.55, 1]),
  circOut: /* @__PURE__ */ Pl([0.55, 0, 1, 0.45]),
  backIn: /* @__PURE__ */ Pl([0.31, 0.01, 0.66, -0.59]),
  backOut: /* @__PURE__ */ Pl([0.33, 1.53, 0.69, 0.99])
};
function $g(i, l) {
  if (i)
    return typeof i == "function" ? Ig() ? Zg(i, l) : "ease-out" : /* @__PURE__ */ jg(i) ? Pl(i) : Array.isArray(i) ? i.map((r) => $g(r, l) || h0.easeOut) : h0[i];
}
function zx(i, l, r, { delay: o = 0, duration: c = 300, repeat: d = 0, repeatType: h = "loop", ease: y = "easeOut", times: v } = {}, b = void 0) {
  const g = {
    [l]: r
  };
  v && (g.offset = v);
  const p = $g(y, c);
  Array.isArray(p) && (g.easing = p);
  const T = {
    delay: o,
    duration: c,
    easing: Array.isArray(p) ? "linear" : p,
    fill: "both",
    iterations: d + 1,
    direction: h === "reverse" ? "alternate" : "normal"
  };
  return b && (T.pseudoElement = b), i.animate(g, T);
}
function tv(i) {
  return typeof i == "function" && "applyToOptions" in i;
}
function Rx({ type: i, ...l }) {
  return tv(i) && Ig() ? i.applyToOptions(l) : (l.duration ?? (l.duration = 300), l.ease ?? (l.ease = "easeOut"), l);
}
class ev extends ih {
  constructor(l) {
    if (super(), this.finishedTime = null, this.isStopped = !1, this.manualStartTime = null, !l)
      return;
    const { element: r, name: o, keyframes: c, pseudoElement: d, allowFlatten: h = !1, finalKeyframe: y, onComplete: v } = l;
    this.isPseudoElement = !!d, this.allowFlatten = h, this.options = l, oo(typeof l.type != "string");
    const b = Rx(l);
    this.animation = zx(r, o, c, b, d), b.autoplay === !1 && this.animation.pause(), this.animation.onfinish = () => {
      if (this.finishedTime = this.time, !d) {
        const g = ro(c, this.options, y, this.speed);
        this.updateMotionValue && this.updateMotionValue(g), Fg(r, o, g), this.animation.cancel();
      }
      v?.(), this.notifyFinished();
    };
  }
  play() {
    this.isStopped || (this.manualStartTime = null, this.animation.play(), this.state === "finished" && this.updateFinished());
  }
  pause() {
    this.animation.pause();
  }
  complete() {
    this.animation.finish?.();
  }
  cancel() {
    try {
      this.animation.cancel();
    } catch {
    }
  }
  stop() {
    if (this.isStopped)
      return;
    this.isStopped = !0;
    const { state: l } = this;
    l === "idle" || l === "finished" || (this.updateMotionValue ? this.updateMotionValue() : this.commitStyles(), this.isPseudoElement || this.cancel());
  }
  /**
   * WAAPI doesn't natively have any interruption capabilities.
   *
   * In this method, we commit styles back to the DOM before cancelling
   * the animation.
   *
   * This is designed to be overridden by NativeAnimationExtended, which
   * will create a renderless JS animation and sample it twice to calculate
   * its current value, "previous" value, and therefore allow
   * Motion to also correctly calculate velocity for any subsequent animation
   * while deferring the commit until the next animation frame.
   */
  commitStyles() {
    const l = this.options?.element;
    !this.isPseudoElement && l?.isConnected && this.animation.commitStyles?.();
  }
  get duration() {
    const l = this.animation.effect?.getComputedTiming?.().duration || 0;
    return /* @__PURE__ */ ke(Number(l));
  }
  get iterationDuration() {
    const { delay: l = 0 } = this.options || {};
    return this.duration + /* @__PURE__ */ ke(l);
  }
  get time() {
    return /* @__PURE__ */ ke(Number(this.animation.currentTime) || 0);
  }
  set time(l) {
    const r = this.finishedTime !== null;
    this.manualStartTime = null, this.finishedTime = null, this.animation.currentTime = /* @__PURE__ */ He(l), r && this.animation.pause();
  }
  /**
   * The playback speed of the animation.
   * 1 = normal speed, 2 = double speed, 0.5 = half speed.
   */
  get speed() {
    return this.animation.playbackRate;
  }
  set speed(l) {
    l < 0 && (this.finishedTime = null), this.animation.playbackRate = l;
  }
  get state() {
    return this.finishedTime !== null ? "finished" : this.animation.playState;
  }
  get startTime() {
    return this.manualStartTime ?? Number(this.animation.startTime);
  }
  set startTime(l) {
    this.manualStartTime = this.animation.startTime = l;
  }
  /**
   * Attaches a timeline to the animation, for instance the `ScrollTimeline`.
   */
  attachTimeline({ timeline: l, rangeStart: r, rangeEnd: o, observe: c }) {
    return this.allowFlatten && this.animation.effect?.updateTiming({ easing: "linear" }), this.animation.onfinish = null, l && Nx() ? (this.animation.timeline = l, r && (this.animation.rangeStart = r), o && (this.animation.rangeEnd = o), Pe) : c(this);
  }
}
const nv = {
  anticipate: Rg,
  backInOut: zg,
  circInOut: wg
};
function _x(i) {
  return i in nv;
}
function wx(i) {
  typeof i.ease == "string" && _x(i.ease) && (i.ease = nv[i.ease]);
}
const uf = 10;
class Vx extends ev {
  constructor(l) {
    wx(l), Jg(l), super(l), l.startTime !== void 0 && l.autoplay !== !1 && (this.startTime = l.startTime), this.options = l;
  }
  /**
   * WAAPI doesn't natively have any interruption capabilities.
   *
   * Rather than read committed styles back out of the DOM, we can
   * create a renderless JS animation and sample it twice to calculate
   * its current value, "previous" value, and therefore allow
   * Motion to calculate velocity for any subsequent animation.
   */
  updateMotionValue(l) {
    const { motionValue: r, onUpdate: o, onComplete: c, element: d, ...h } = this.options;
    if (!r)
      return;
    if (l !== void 0) {
      r.set(l);
      return;
    }
    const y = new to({
      ...h,
      autoplay: !1
    }), v = Math.max(uf, be.now() - this.startTime), b = En(0, uf, v - uf), g = y.sample(v).value, { name: p } = this.options;
    d && p && Fg(d, p, g), r.setWithVelocity(y.sample(Math.max(0, v - b)).value, g, b), y.stop();
  }
}
const d0 = (i, l) => l === "zIndex" ? !1 : !!(typeof i == "number" || Array.isArray(i) || typeof i == "string" && // It's animatable if we have a string
(sn.test(i) || i === "0") && // And it contains numbers and/or colors
!i.startsWith("url("));
function jx(i) {
  const l = i[0];
  if (i.length === 1)
    return !0;
  for (let r = 0; r < i.length; r++)
    if (i[r] !== l)
      return !0;
}
function Ux(i, l, r, o) {
  const c = i[0];
  if (c === null)
    return !1;
  if (l === "display" || l === "visibility")
    return !0;
  const d = i[i.length - 1], h = d0(c, l), y = d0(d, l);
  return !h || !y ? !1 : jx(i) || (r === "spring" || tv(r)) && o;
}
function Rf(i) {
  i.duration = 0, i.type = "keyframes";
}
const av = /* @__PURE__ */ new Set([
  "opacity",
  "clipPath",
  "filter",
  "transform",
  "backgroundColor"
]), Bx = /^(?:oklch|oklab|lab|lch|color|color-mix|light-dark)\(/;
function Hx(i) {
  for (let l = 0; l < i.length; l++)
    if (typeof i[l] == "string" && Bx.test(i[l]))
      return !0;
  return !1;
}
const Lx = /* @__PURE__ */ new Set([
  "color",
  "backgroundColor",
  "outlineColor",
  "fill",
  "stroke",
  "borderColor",
  "borderTopColor",
  "borderRightColor",
  "borderBottomColor",
  "borderLeftColor"
]), Yx = /* @__PURE__ */ Ag(() => Object.hasOwnProperty.call(Element.prototype, "animate"));
function qx(i) {
  const { motionValue: l, name: r, repeatDelay: o, repeatType: c, damping: d, type: h, keyframes: y } = i, v = l?.owner?.current;
  if (!(v instanceof HTMLElement) && !(v instanceof SVGElement))
    return !1;
  const { onUpdate: b, transformTemplate: g } = l.owner.getProps();
  return Yx() && r && /**
   * Force WAAPI for color properties with browser-only color formats
   * (oklch, oklab, lab, lch, etc.) that the JS animation path can't parse.
   */
  (av.has(r) || Lx.has(r) && Hx(y)) && (r !== "transform" || !g) && /**
   * If we're outputting values to onUpdate then we can't use WAAPI as there's
   * no way to read the value from WAAPI every frame.
   */
  !b && !o && c !== "mirror" && d !== 0 && h !== "inertia";
}
const Gx = 40;
class Xx extends ih {
  constructor({ autoplay: l = !0, delay: r = 0, type: o = "keyframes", repeat: c = 0, repeatDelay: d = 0, repeatType: h = "loop", keyframes: y, name: v, motionValue: b, element: g, ...p }) {
    super(), this.stop = () => {
      this._animation && (this._animation.stop(), this.stopTimeline?.()), this.keyframeResolver?.cancel();
    }, this.createdAt = be.now();
    const T = {
      autoplay: l,
      delay: r,
      type: o,
      repeat: c,
      repeatDelay: d,
      repeatType: h,
      name: v,
      motionValue: b,
      element: g,
      ...p
    }, V = g?.KeyframeResolver || lh;
    this.keyframeResolver = new V(y, (z, B, j) => this.onKeyframesResolved(z, B, T, !j), v, b, g), this.keyframeResolver?.scheduleResolve();
  }
  onKeyframesResolved(l, r, o, c) {
    this.keyframeResolver = void 0;
    const { name: d, type: h, velocity: y, delay: v, isHandoff: b, onUpdate: g } = o;
    this.resolvedAt = be.now();
    let p = !0;
    Ux(l, d, h, y) || (p = !1, (ga.instantAnimations || !v) && g?.(ro(l, o, r)), l[0] = l[l.length - 1], Rf(o), o.repeat = 0);
    const V = {
      startTime: c ? this.resolvedAt ? this.resolvedAt - this.createdAt > Gx ? this.resolvedAt : this.createdAt : this.createdAt : void 0,
      finalKeyframe: r,
      ...o,
      keyframes: l
    }, z = p && !b && qx(V), B = V.motionValue?.owner?.current;
    let j;
    if (z)
      try {
        j = new Vx({
          ...V,
          element: B
        });
      } catch {
        j = new to(V);
      }
    else
      j = new to(V);
    j.finished.then(() => {
      this.notifyFinished();
    }).catch(Pe), this.pendingTimeline && (this.stopTimeline = j.attachTimeline(this.pendingTimeline), this.pendingTimeline = void 0), this._animation = j;
  }
  get finished() {
    return this._animation ? this.animation.finished : this._finished;
  }
  then(l, r) {
    return this.finished.finally(l).then(() => {
    });
  }
  get animation() {
    return this._animation || (this.keyframeResolver?.resume(), Dx()), this._animation;
  }
  get duration() {
    return this.animation.duration;
  }
  get iterationDuration() {
    return this.animation.iterationDuration;
  }
  get time() {
    return this.animation.time;
  }
  set time(l) {
    this.animation.time = l;
  }
  get speed() {
    return this.animation.speed;
  }
  get state() {
    return this.animation.state;
  }
  set speed(l) {
    this.animation.speed = l;
  }
  get startTime() {
    return this.animation.startTime;
  }
  attachTimeline(l) {
    return this._animation ? this.stopTimeline = this.animation.attachTimeline(l) : this.pendingTimeline = l, () => this.stop();
  }
  play() {
    this.animation.play();
  }
  pause() {
    this.animation.pause();
  }
  complete() {
    this.animation.complete();
  }
  cancel() {
    this._animation && this.animation.cancel(), this.keyframeResolver?.cancel();
  }
}
function iv(i, l, r, o = 0, c = 1) {
  const d = Array.from(i).sort((b, g) => b.sortNodePosition(g)).indexOf(l), h = i.size, y = (h - 1) * o;
  return typeof r == "function" ? r(d, h) : c === 1 ? d * o : y - d * o;
}
const m0 = 30, Qx = (i) => !isNaN(parseFloat(i));
class Zx {
  /**
   * @param init - The initiating value
   * @param config - Optional configuration options
   *
   * -  `transformer`: A function to transform incoming values with.
   */
  constructor(l, r = {}) {
    this.canTrackVelocity = null, this.events = {}, this.updateAndNotify = (o) => {
      const c = be.now();
      if (this.updatedAt !== c && this.setPrevFrameValue(), this.prev = this.current, this.setCurrent(o), this.current !== this.prev && (this.events.change?.notify(this.current), this.dependents))
        for (const d of this.dependents)
          d.dirty();
    }, this.hasAnimated = !1, this.setCurrent(l), this.owner = r.owner;
  }
  setCurrent(l) {
    this.current = l, this.updatedAt = be.now(), this.canTrackVelocity === null && l !== void 0 && (this.canTrackVelocity = Qx(this.current));
  }
  setPrevFrameValue(l = this.current) {
    this.prevFrameValue = l, this.prevUpdatedAt = this.updatedAt;
  }
  /**
   * Adds a function that will be notified when the `MotionValue` is updated.
   *
   * It returns a function that, when called, will cancel the subscription.
   *
   * When calling `onChange` inside a React component, it should be wrapped with the
   * `useEffect` hook. As it returns an unsubscribe function, this should be returned
   * from the `useEffect` function to ensure you don't add duplicate subscribers..
   *
   * ```jsx
   * export const MyComponent = () => {
   *   const x = useMotionValue(0)
   *   const y = useMotionValue(0)
   *   const opacity = useMotionValue(1)
   *
   *   useEffect(() => {
   *     function updateOpacity() {
   *       const maxXY = Math.max(x.get(), y.get())
   *       const newOpacity = transform(maxXY, [0, 100], [1, 0])
   *       opacity.set(newOpacity)
   *     }
   *
   *     const unsubscribeX = x.on("change", updateOpacity)
   *     const unsubscribeY = y.on("change", updateOpacity)
   *
   *     return () => {
   *       unsubscribeX()
   *       unsubscribeY()
   *     }
   *   }, [])
   *
   *   return <motion.div style={{ x }} />
   * }
   * ```
   *
   * @param subscriber - A function that receives the latest value.
   * @returns A function that, when called, will cancel this subscription.
   *
   * @deprecated
   */
  onChange(l) {
    return this.on("change", l);
  }
  on(l, r) {
    this.events[l] || (this.events[l] = new Ff());
    const o = this.events[l].add(r);
    return l === "change" ? () => {
      o(), Vt.read(() => {
        this.events.change.getSize() || this.stop();
      });
    } : o;
  }
  clearListeners() {
    for (const l in this.events)
      this.events[l].clear();
  }
  /**
   * Attaches a passive effect to the `MotionValue`.
   */
  attach(l, r) {
    this.passiveEffect = l, this.stopPassiveEffect = r;
  }
  /**
   * Sets the state of the `MotionValue`.
   *
   * @remarks
   *
   * ```jsx
   * const x = useMotionValue(0)
   * x.set(10)
   * ```
   *
   * @param latest - Latest value to set.
   * @param render - Whether to notify render subscribers. Defaults to `true`
   *
   * @public
   */
  set(l) {
    this.passiveEffect ? this.passiveEffect(l, this.updateAndNotify) : this.updateAndNotify(l);
  }
  setWithVelocity(l, r, o) {
    this.set(r), this.prev = void 0, this.prevFrameValue = l, this.prevUpdatedAt = this.updatedAt - o;
  }
  /**
   * Set the state of the `MotionValue`, stopping any active animations,
   * effects, and resets velocity to `0`.
   */
  jump(l, r = !0) {
    this.updateAndNotify(l), this.prev = l, this.prevUpdatedAt = this.prevFrameValue = void 0, r && this.stop(), this.stopPassiveEffect && this.stopPassiveEffect();
  }
  dirty() {
    this.events.change?.notify(this.current);
  }
  addDependent(l) {
    this.dependents || (this.dependents = /* @__PURE__ */ new Set()), this.dependents.add(l);
  }
  removeDependent(l) {
    this.dependents && this.dependents.delete(l);
  }
  /**
   * Returns the latest state of `MotionValue`
   *
   * @returns - The latest state of `MotionValue`
   *
   * @public
   */
  get() {
    return this.current;
  }
  /**
   * @public
   */
  getPrevious() {
    return this.prev;
  }
  /**
   * Returns the latest velocity of `MotionValue`
   *
   * @returns - The latest velocity of `MotionValue`. Returns `0` if the state is non-numerical.
   *
   * @public
   */
  getVelocity() {
    const l = be.now();
    if (!this.canTrackVelocity || this.prevFrameValue === void 0 || l - this.updatedAt > m0)
      return 0;
    const r = Math.min(this.updatedAt - this.prevUpdatedAt, m0);
    return /* @__PURE__ */ Mg(parseFloat(this.current) - parseFloat(this.prevFrameValue), r);
  }
  /**
   * Registers a new animation to control this `MotionValue`. Only one
   * animation can drive a `MotionValue` at one time.
   *
   * ```jsx
   * value.start()
   * ```
   *
   * @param animation - A function that starts the provided animation
   */
  start(l) {
    return this.stop(), new Promise((r) => {
      this.hasAnimated = !0, this.animation = l(r), this.events.animationStart && this.events.animationStart.notify();
    }).then(() => {
      this.events.animationComplete && this.events.animationComplete.notify(), this.clearAnimation();
    });
  }
  /**
   * Stop the currently active animation.
   *
   * @public
   */
  stop() {
    this.animation && (this.animation.stop(), this.events.animationCancel && this.events.animationCancel.notify()), this.clearAnimation();
  }
  /**
   * Returns `true` if this value is currently animating.
   *
   * @public
   */
  isAnimating() {
    return !!this.animation;
  }
  clearAnimation() {
    delete this.animation;
  }
  /**
   * Destroy and clean up subscribers to this `MotionValue`.
   *
   * The `MotionValue` hooks like `useMotionValue` and `useTransform` automatically
   * handle the lifecycle of the returned `MotionValue`, so this method is only necessary if you've manually
   * created a `MotionValue` via the `motionValue` function.
   *
   * @public
   */
  destroy() {
    this.dependents?.clear(), this.events.destroy?.notify(), this.clearListeners(), this.stop(), this.stopPassiveEffect && this.stopPassiveEffect();
  }
}
function ki(i, l) {
  return new Zx(i, l);
}
function lv(i, l) {
  if (i?.inherit && l) {
    const { inherit: r, ...o } = i;
    return { ...l, ...o };
  }
  return i;
}
function sh(i, l) {
  const r = i?.[l] ?? i?.default ?? i;
  return r !== i ? lv(r, i) : r;
}
const Kx = {
  type: "spring",
  stiffness: 500,
  damping: 25,
  restSpeed: 10
}, Jx = (i) => ({
  type: "spring",
  stiffness: 550,
  damping: i === 0 ? 2 * Math.sqrt(550) : 30,
  restSpeed: 10
}), kx = {
  type: "keyframes",
  duration: 0.8
}, Px = {
  type: "keyframes",
  ease: [0.25, 0.1, 0.35, 1],
  duration: 0.3
}, Fx = (i, { keyframes: l }) => l.length > 2 ? kx : Wi.has(i) ? i.startsWith("scale") ? Jx(l[1]) : Kx : Px, Wx = /* @__PURE__ */ new Set([
  "when",
  "delay",
  "delayChildren",
  "staggerChildren",
  "staggerDirection",
  "repeat",
  "repeatType",
  "repeatDelay",
  "from",
  "elapsed"
]);
function Ix(i) {
  for (const l in i)
    if (!Wx.has(l))
      return !0;
  return !1;
}
const uh = (i, l, r, o = {}, c, d) => (h) => {
  const y = sh(o, i) || {}, v = y.delay || o.delay || 0;
  let { elapsed: b = 0 } = o;
  b = b - /* @__PURE__ */ He(v);
  const g = {
    keyframes: Array.isArray(r) ? r : [null, r],
    ease: "easeOut",
    velocity: l.getVelocity(),
    ...y,
    delay: -b,
    onUpdate: (T) => {
      l.set(T), y.onUpdate && y.onUpdate(T);
    },
    onComplete: () => {
      h(), y.onComplete && y.onComplete();
    },
    name: i,
    motionValue: l,
    element: d ? void 0 : c
  };
  Ix(y) || Object.assign(g, Fx(i, g)), g.duration && (g.duration = /* @__PURE__ */ He(g.duration)), g.repeatDelay && (g.repeatDelay = /* @__PURE__ */ He(g.repeatDelay)), g.from !== void 0 && (g.keyframes[0] = g.from);
  let p = !1;
  if ((g.type === !1 || g.duration === 0 && !g.repeatDelay) && (Rf(g), g.delay === 0 && (p = !0)), (ga.instantAnimations || ga.skipAnimations || c?.shouldSkipAnimations || y.skipAnimations) && (p = !0, Rf(g), g.delay = 0), g.allowFlatten = !y.type && !y.ease, p && !d && l.get() !== void 0) {
    const T = ro(g.keyframes, y);
    if (T !== void 0) {
      Vt.update(() => {
        g.onUpdate(T), g.onComplete();
      });
      return;
    }
  }
  return y.isSync ? new to(g) : new Xx(g);
}, $x = (
  // eslint-disable-next-line redos-detector/no-unsafe-regex -- false positive, as it can match a lot of words
  /^var\(--(?:([\w-]+)|([\w-]+), ?([a-zA-Z\d ()%#.,-]+))\)/u
);
function t2(i) {
  const l = $x.exec(i);
  if (!l)
    return [,];
  const [, r, o, c] = l;
  return [`--${r ?? o}`, c];
}
function sv(i, l, r = 1) {
  const [o, c] = t2(i);
  if (!o)
    return;
  const d = window.getComputedStyle(l).getPropertyValue(o);
  if (d) {
    const h = d.trim();
    return Tg(h) ? parseFloat(h) : h;
  }
  return $f(c) ? sv(c, l, r + 1) : c;
}
function y0(i) {
  const l = [{}, {}];
  return i?.values.forEach((r, o) => {
    l[0][o] = r.get(), l[1][o] = r.getVelocity();
  }), l;
}
function oh(i, l, r, o) {
  if (typeof l == "function") {
    const [c, d] = y0(o);
    l = l(r !== void 0 ? r : i.custom, c, d);
  }
  if (typeof l == "string" && (l = i.variants && i.variants[l]), typeof l == "function") {
    const [c, d] = y0(o);
    l = l(r !== void 0 ? r : i.custom, c, d);
  }
  return l;
}
function Wa(i, l, r) {
  const o = i.getProps();
  return oh(o, l, r !== void 0 ? r : o.custom, i);
}
const uv = /* @__PURE__ */ new Set([
  "width",
  "height",
  "top",
  "left",
  "right",
  "bottom",
  ...Fi
]), _f = (i) => Array.isArray(i);
function e2(i, l, r) {
  i.hasValue(l) ? i.getValue(l).set(r) : i.addValue(l, ki(r));
}
function n2(i) {
  return _f(i) ? i[i.length - 1] || 0 : i;
}
function a2(i, l) {
  const r = Wa(i, l);
  let { transitionEnd: o = {}, transition: c = {}, ...d } = r || {};
  d = { ...d, ...o };
  for (const h in d) {
    const y = n2(d[h]);
    e2(i, h, y);
  }
}
const he = (i) => !!(i && i.getVelocity);
function i2(i) {
  return !!(he(i) && i.add);
}
function wf(i, l) {
  const r = i.getValue("willChange");
  if (i2(r))
    return r.add(l);
  if (!r && ga.WillChange) {
    const o = new ga.WillChange("auto");
    i.addValue("willChange", o), o.add(l);
  }
}
function rh(i) {
  return i.replace(/([A-Z])/g, (l) => `-${l.toLowerCase()}`);
}
const l2 = "framerAppearId", ov = "data-" + rh(l2);
function rv(i) {
  return i.props[ov];
}
function s2({ protectedKeys: i, needsAnimating: l }, r) {
  const o = i.hasOwnProperty(r) && l[r] !== !0;
  return l[r] = !1, o;
}
function cv(i, l, { delay: r = 0, transitionOverride: o, type: c } = {}) {
  let { transition: d, transitionEnd: h, ...y } = l;
  const v = i.getDefaultTransition();
  d = d ? lv(d, v) : v;
  const b = d?.reduceMotion, g = d?.skipAnimations;
  o && (d = o);
  const p = [], T = c && i.animationState && i.animationState.getState()[c], V = d?.path;
  V && V.animateVisualElement(i, y, d, r, p);
  for (const z in y) {
    const B = i.getValue(z, i.latestValues[z] ?? null), j = y[z];
    if (j === void 0 || T && s2(T, z))
      continue;
    const L = {
      delay: r,
      ...sh(d || {}, z)
    };
    g && (L.skipAnimations = !0);
    const Y = B.get();
    if (Y !== void 0 && !B.isAnimating() && !Array.isArray(j) && j === Y && !L.velocity) {
      Vt.update(() => B.set(j));
      continue;
    }
    let U = !1;
    if (window.MotionHandoffAnimation) {
      const rt = rv(i);
      if (rt) {
        const J = window.MotionHandoffAnimation(rt, z, Vt);
        J !== null && (L.startTime = J, U = !0);
      }
    }
    wf(i, z);
    const G = b ?? i.shouldReduceMotion;
    B.start(uh(z, B, j, G && uv.has(z) ? { type: !1 } : L, i, U));
    const nt = B.animation;
    nt && p.push(nt);
  }
  if (h) {
    const z = () => Vt.update(() => {
      h && a2(i, h);
    });
    p.length ? Promise.all(p).then(z) : z();
  }
  return p;
}
function Vf(i, l, r = {}) {
  const o = Wa(i, l, r.type === "exit" ? i.presenceContext?.custom : void 0);
  let { transition: c = i.getDefaultTransition() || {} } = o || {};
  r.transitionOverride && (c = r.transitionOverride);
  const d = o ? () => Promise.all(cv(i, o, r)) : () => Promise.resolve(), h = i.variantChildren && i.variantChildren.size ? (v = 0) => {
    const { delayChildren: b = 0, staggerChildren: g, staggerDirection: p } = c;
    return u2(i, l, v, b, g, p, r);
  } : () => Promise.resolve(), { when: y } = c;
  if (y) {
    const [v, b] = y === "beforeChildren" ? [d, h] : [h, d];
    return v().then(() => b());
  } else
    return Promise.all([d(), h(r.delay)]);
}
function u2(i, l, r = 0, o = 0, c = 0, d = 1, h) {
  const y = [];
  for (const v of i.variantChildren)
    v.notify("AnimationStart", l), y.push(Vf(v, l, {
      ...h,
      delay: r + (typeof o == "function" ? 0 : o) + iv(i.variantChildren, v, o, c, d)
    }).then(() => v.notify("AnimationComplete", l)));
  return Promise.all(y);
}
function o2(i, l, r = {}) {
  i.notify("AnimationStart", l);
  let o;
  if (Array.isArray(l)) {
    const c = l.map((d) => Vf(i, d, r));
    o = Promise.all(c);
  } else if (typeof l == "string")
    o = Vf(i, l, r);
  else {
    const c = typeof l == "function" ? Wa(i, l, r.custom) : l;
    o = Promise.all(cv(i, c, r));
  }
  return o.then(() => {
    i.notify("AnimationComplete", l);
  });
}
const r2 = {
  test: (i) => i === "auto",
  parse: (i) => i
}, fv = (i) => (l) => l.test(i), hv = [Pi, F, xn, Yn, jT, VT, r2], p0 = (i) => hv.find(fv(i));
function c2(i) {
  return typeof i == "number" ? i === 0 : i !== null ? i === "none" || i === "0" || Eg(i) : !0;
}
const f2 = /* @__PURE__ */ new Set(["brightness", "contrast", "saturate", "opacity"]);
function h2(i) {
  const [l, r] = i.slice(0, -1).split("(");
  if (l === "drop-shadow")
    return i;
  const [o] = r.match(th) || [];
  if (!o)
    return i;
  const c = r.replace(o, "");
  let d = f2.has(l) ? 1 : 0;
  return o !== r && (d *= 100), l + "(" + d + c + ")";
}
const d2 = /\b([a-z-]*)\(.*?\)/gu, jf = {
  ...sn,
  getAnimatableNone: (i) => {
    const l = i.match(d2);
    return l ? l.map(h2).join(" ") : i;
  }
}, Uf = {
  ...sn,
  getAnimatableNone: (i) => {
    const l = sn.parse(i);
    return sn.createTransformer(i)(l.map((o) => typeof o == "number" ? 0 : typeof o == "object" ? { ...o, alpha: 1 } : o));
  }
}, g0 = {
  ...Pi,
  transform: Math.round
}, m2 = {
  rotate: Yn,
  /**
   * Internal channel for `transition.path` orientToPath. Composed onto
   * `rotate` at the transform-build sites so the user's `rotate` is
   * never read or overwritten. Not part of `transformPropOrder`.
   */
  pathRotation: Yn,
  rotateX: Yn,
  rotateY: Yn,
  rotateZ: Yn,
  scale: Lu,
  scaleX: Lu,
  scaleY: Lu,
  scaleZ: Lu,
  skew: Yn,
  skewX: Yn,
  skewY: Yn,
  distance: F,
  translateX: F,
  translateY: F,
  translateZ: F,
  x: F,
  y: F,
  z: F,
  perspective: F,
  transformPerspective: F,
  opacity: es,
  originX: a0,
  originY: a0,
  originZ: F
}, eo = {
  // Border props
  borderWidth: F,
  borderTopWidth: F,
  borderRightWidth: F,
  borderBottomWidth: F,
  borderLeftWidth: F,
  borderRadius: F,
  borderTopLeftRadius: F,
  borderTopRightRadius: F,
  borderBottomRightRadius: F,
  borderBottomLeftRadius: F,
  // Positioning props
  width: F,
  maxWidth: F,
  height: F,
  maxHeight: F,
  top: F,
  right: F,
  bottom: F,
  left: F,
  inset: F,
  insetBlock: F,
  insetBlockStart: F,
  insetBlockEnd: F,
  insetInline: F,
  insetInlineStart: F,
  insetInlineEnd: F,
  // Spacing props
  padding: F,
  paddingTop: F,
  paddingRight: F,
  paddingBottom: F,
  paddingLeft: F,
  paddingBlock: F,
  paddingBlockStart: F,
  paddingBlockEnd: F,
  paddingInline: F,
  paddingInlineStart: F,
  paddingInlineEnd: F,
  margin: F,
  marginTop: F,
  marginRight: F,
  marginBottom: F,
  marginLeft: F,
  marginBlock: F,
  marginBlockStart: F,
  marginBlockEnd: F,
  marginInline: F,
  marginInlineStart: F,
  marginInlineEnd: F,
  // Typography
  fontSize: F,
  // Misc
  backgroundPositionX: F,
  backgroundPositionY: F,
  ...m2,
  zIndex: g0,
  // SVG
  fillOpacity: es,
  strokeOpacity: es,
  numOctaves: g0
}, y2 = {
  ...eo,
  // Color props
  color: kt,
  backgroundColor: kt,
  outlineColor: kt,
  fill: kt,
  stroke: kt,
  // Border props
  borderColor: kt,
  borderTopColor: kt,
  borderRightColor: kt,
  borderBottomColor: kt,
  borderLeftColor: kt,
  filter: jf,
  WebkitFilter: jf,
  mask: Uf,
  WebkitMask: Uf
}, dv = (i) => y2[i], p2 = /* @__PURE__ */ new Set([jf, Uf]);
function mv(i, l) {
  let r = dv(i);
  return p2.has(r) || (r = sn), r.getAnimatableNone ? r.getAnimatableNone(l) : void 0;
}
const g2 = /* @__PURE__ */ new Set(["auto", "none", "0"]);
function v2(i, l, r) {
  let o = 0, c;
  for (; o < i.length && !c; ) {
    const d = i[o];
    typeof d == "string" && !g2.has(d) && Ji(d).values.length && (c = i[o]), o++;
  }
  if (c && r)
    for (const d of l)
      i[d] = mv(r, c);
}
class b2 extends lh {
  constructor(l, r, o, c, d) {
    super(l, r, o, c, d, !0);
  }
  readKeyframes() {
    const { unresolvedKeyframes: l, element: r, name: o } = this;
    if (!r || !r.current)
      return;
    super.readKeyframes();
    for (let g = 0; g < l.length; g++) {
      let p = l[g];
      if (typeof p == "string" && (p = p.trim(), $f(p))) {
        const T = sv(p, r.current);
        T !== void 0 && (l[g] = T), g === l.length - 1 && (this.finalKeyframe = p);
      }
    }
    if (this.resolveNoneKeyframes(), !uv.has(o) || l.length !== 2)
      return;
    const [c, d] = l, h = p0(c), y = p0(d), v = n0(c), b = n0(d);
    if (v !== b && pa[o]) {
      this.needsMeasurement = !0;
      return;
    }
    if (h !== y)
      if (f0(h) && f0(y))
        for (let g = 0; g < l.length; g++) {
          const p = l[g];
          typeof p == "string" && (l[g] = parseFloat(p));
        }
      else pa[o] && (this.needsMeasurement = !0);
  }
  resolveNoneKeyframes() {
    const { unresolvedKeyframes: l, name: r } = this, o = [];
    for (let c = 0; c < l.length; c++)
      (l[c] === null || c2(l[c])) && o.push(c);
    o.length && v2(l, o, r);
  }
  measureInitialState() {
    const { element: l, unresolvedKeyframes: r, name: o } = this;
    if (!l || !l.current)
      return;
    o === "height" && (this.suspendedScrollY = window.pageYOffset), this.measuredOrigin = pa[o](l.measureViewportBox(), window.getComputedStyle(l.current)), r[0] = this.measuredOrigin;
    const c = r[r.length - 1];
    c !== void 0 && l.getValue(o, c).jump(c, !1);
  }
  measureEndState() {
    const { element: l, name: r, unresolvedKeyframes: o } = this;
    if (!l || !l.current)
      return;
    const c = l.getValue(r);
    c && c.jump(this.measuredOrigin, !1);
    const d = o.length - 1, h = o[d];
    o[d] = pa[r](l.measureViewportBox(), window.getComputedStyle(l.current)), h !== null && this.finalKeyframe === void 0 && (this.finalKeyframe = h), this.removedTransforms?.length && this.removedTransforms.forEach(([y, v]) => {
      l.getValue(y).set(v);
    }), this.resolveNoneKeyframes();
  }
}
const ch = [
  "borderTopLeftRadius",
  "borderTopRightRadius",
  "borderBottomRightRadius",
  "borderBottomLeftRadius"
];
function yv(i, l, r) {
  if (i == null)
    return [];
  if (i instanceof EventTarget)
    return [i];
  if (typeof i == "string") {
    let o = document;
    const c = r?.[i] ?? o.querySelectorAll(i);
    return c ? Array.from(c) : [];
  }
  return Array.from(i).filter((o) => o != null);
}
const Bf = (i, l) => l && typeof i == "number" ? l.transform(i) : i;
function S2(i) {
  return xg(i) && "offsetHeight" in i && !("ownerSVGElement" in i);
}
const { schedule: fh } = /* @__PURE__ */ Ug(queueMicrotask, !1), ln = {
  x: !1,
  y: !1
};
function pv() {
  return ln.x || ln.y;
}
function T2(i) {
  return i === "x" || i === "y" ? ln[i] ? null : (ln[i] = !0, () => {
    ln[i] = !1;
  }) : ln.x || ln.y ? null : (ln.x = ln.y = !0, () => {
    ln.x = ln.y = !1;
  });
}
function gv(i, l) {
  const r = yv(i), o = new AbortController(), c = {
    passive: !0,
    ...l,
    signal: o.signal
  };
  return [r, c, () => o.abort()];
}
function x2(i) {
  return !(i.pointerType === "touch" || pv());
}
function E2(i, l, r = {}) {
  const [o, c, d] = gv(i, r);
  return o.forEach((h) => {
    let y = !1, v = !1, b;
    const g = () => {
      h.removeEventListener("pointerleave", z);
    }, p = (j) => {
      b && (b(j), b = void 0), g();
    }, T = (j) => {
      y = !1, window.removeEventListener("pointerup", T), window.removeEventListener("pointercancel", T), v && (v = !1, p(j));
    }, V = () => {
      y = !0, window.addEventListener("pointerup", T, c), window.addEventListener("pointercancel", T, c);
    }, z = (j) => {
      if (j.pointerType !== "touch") {
        if (y) {
          v = !0;
          return;
        }
        p(j);
      }
    }, B = (j) => {
      if (!x2(j))
        return;
      v = !1;
      const L = l(h, j);
      typeof L == "function" && (b = L, h.addEventListener("pointerleave", z, c));
    };
    h.addEventListener("pointerenter", B, c), h.addEventListener("pointerdown", V, c);
  }), d;
}
const vv = (i, l) => l ? i === l ? !0 : vv(i, l.parentElement) : !1, hh = (i) => i.pointerType === "mouse" ? typeof i.button != "number" || i.button <= 0 : i.isPrimary !== !1, A2 = /* @__PURE__ */ new Set([
  "BUTTON",
  "INPUT",
  "SELECT",
  "TEXTAREA",
  "A"
]);
function M2(i) {
  return A2.has(i.tagName) || i.isContentEditable === !0;
}
const D2 = /* @__PURE__ */ new Set(["INPUT", "SELECT", "TEXTAREA"]);
function C2(i) {
  return D2.has(i.tagName) || i.isContentEditable === !0;
}
const Xu = /* @__PURE__ */ new WeakSet();
function v0(i) {
  return (l) => {
    l.key === "Enter" && i(l);
  };
}
function of(i, l) {
  i.dispatchEvent(new PointerEvent("pointer" + l, { isPrimary: !0, bubbles: !0 }));
}
const O2 = (i, l) => {
  const r = i.currentTarget;
  if (!r)
    return;
  const o = v0(() => {
    if (Xu.has(r))
      return;
    of(r, "down");
    const c = v0(() => {
      of(r, "up");
    }), d = () => of(r, "cancel");
    r.addEventListener("keyup", c, l), r.addEventListener("blur", d, l);
  });
  r.addEventListener("keydown", o, l), r.addEventListener("blur", () => r.removeEventListener("keydown", o), l);
};
function b0(i) {
  return hh(i) && !pv();
}
const S0 = /* @__PURE__ */ new WeakSet();
function N2(i, l, r = {}) {
  const [o, c, d] = gv(i, r), h = (y) => {
    const v = y.currentTarget;
    if (!b0(y) || S0.has(y))
      return;
    Xu.add(v), r.stopPropagation && S0.add(y);
    const b = l(v, y), g = { ...c, capture: !0 }, p = (z, B) => {
      window.removeEventListener("pointerup", T, g), window.removeEventListener("pointercancel", V, g), Xu.has(v) && Xu.delete(v), b0(z) && typeof b == "function" && b(z, { success: B });
    }, T = (z) => {
      p(z, v === window || v === document || r.useGlobalTarget || vv(v, z.target));
    }, V = (z) => {
      p(z, !1);
    };
    window.addEventListener("pointerup", T, g), window.addEventListener("pointercancel", V, g);
  };
  return o.forEach((y) => {
    (r.useGlobalTarget ? window : y).addEventListener("pointerdown", h, c), S2(y) && (y.addEventListener("focus", (b) => O2(b, c)), !M2(y) && !y.hasAttribute("tabindex") && (y.tabIndex = 0));
  }), d;
}
function dh(i) {
  return xg(i) && "ownerSVGElement" in i;
}
const Qu = /* @__PURE__ */ new WeakMap();
let Zu;
const bv = (i, l, r) => (o, c) => c && c[0] ? c[0][i + "Size"] : dh(o) && "getBBox" in o ? o.getBBox()[l] : o[r], z2 = /* @__PURE__ */ bv("inline", "width", "offsetWidth"), R2 = /* @__PURE__ */ bv("block", "height", "offsetHeight");
function _2({ target: i, borderBoxSize: l }) {
  Qu.get(i)?.forEach((r) => {
    r(i, {
      get width() {
        return z2(i, l);
      },
      get height() {
        return R2(i, l);
      }
    });
  });
}
function w2(i) {
  i.forEach(_2);
}
function V2() {
  typeof ResizeObserver > "u" || (Zu = new ResizeObserver(w2));
}
function j2(i, l) {
  Zu || V2();
  const r = yv(i);
  return r.forEach((o) => {
    let c = Qu.get(o);
    c || (c = /* @__PURE__ */ new Set(), Qu.set(o, c)), c.add(l), Zu?.observe(o);
  }), () => {
    r.forEach((o) => {
      const c = Qu.get(o);
      c?.delete(l), c?.size || Zu?.unobserve(o);
    });
  };
}
const Ku = /* @__PURE__ */ new Set();
let Zi;
function U2() {
  Zi = () => {
    const i = {
      get width() {
        return window.innerWidth;
      },
      get height() {
        return window.innerHeight;
      }
    };
    Ku.forEach((l) => l(i));
  }, window.addEventListener("resize", Zi);
}
function B2(i) {
  return Ku.add(i), Zi || U2(), () => {
    Ku.delete(i), !Ku.size && typeof Zi == "function" && (window.removeEventListener("resize", Zi), Zi = void 0);
  };
}
function T0(i, l) {
  return typeof i == "function" ? B2(i) : j2(i, l);
}
function H2(i) {
  return dh(i) && i.tagName === "svg";
}
const L2 = [...hv, kt, sn], Y2 = (i) => L2.find(fv(i)), x0 = () => ({
  translate: 0,
  scale: 1,
  origin: 0,
  originPoint: 0
}), Ki = () => ({
  x: x0(),
  y: x0()
}), E0 = () => ({ min: 0, max: 0 }), Ft = () => ({
  x: E0(),
  y: E0()
}), q2 = /* @__PURE__ */ new WeakMap();
function co(i) {
  return i !== null && typeof i == "object" && typeof i.start == "function";
}
function ns(i) {
  return typeof i == "string" || Array.isArray(i);
}
const mh = [
  "animate",
  "whileInView",
  "whileFocus",
  "whileHover",
  "whileTap",
  "whileDrag",
  "exit"
], yh = ["initial", ...mh];
function fo(i) {
  return co(i.animate) || yh.some((l) => ns(i[l]));
}
function Sv(i) {
  return !!(fo(i) || i.variants);
}
function G2(i, l, r) {
  for (const o in l) {
    const c = l[o], d = r[o];
    if (he(c))
      i.addValue(o, c);
    else if (he(d))
      i.addValue(o, ki(c, { owner: i }));
    else if (d !== c)
      if (i.hasValue(o)) {
        const h = i.getValue(o);
        h.liveStyle === !0 ? h.jump(c) : h.hasAnimated || h.set(c);
      } else {
        const h = i.getStaticValue(o);
        i.addValue(o, ki(h !== void 0 ? h : c, { owner: i }));
      }
  }
  for (const o in r)
    l[o] === void 0 && i.removeValue(o);
  return l;
}
const no = { current: null }, ph = { current: !1 }, X2 = typeof window < "u";
function Tv() {
  if (ph.current = !0, !!X2)
    if (window.matchMedia) {
      const i = window.matchMedia("(prefers-reduced-motion)"), l = () => no.current = i.matches;
      i.addEventListener("change", l), l();
    } else
      no.current = !1;
}
const A0 = [
  "AnimationStart",
  "AnimationComplete",
  "Update",
  "BeforeLayoutMeasure",
  "LayoutMeasure",
  "LayoutAnimationStart",
  "LayoutAnimationComplete"
];
let ao = {};
function xv(i) {
  ao = i;
}
function Q2() {
  return ao;
}
class Z2 {
  /**
   * This method takes React props and returns found MotionValues. For example, HTML
   * MotionValues will be found within the style prop, whereas for Three.js within attribute arrays.
   *
   * This isn't an abstract method as it needs calling in the constructor, but it is
   * intended to be one.
   */
  scrapeMotionValuesFromProps(l, r, o) {
    return {};
  }
  constructor({ parent: l, props: r, presenceContext: o, reducedMotionConfig: c, skipAnimations: d, blockInitialAnimation: h, visualState: y }, v = {}) {
    this.current = null, this.children = /* @__PURE__ */ new Set(), this.isVariantNode = !1, this.isControllingVariants = !1, this.shouldReduceMotion = null, this.shouldSkipAnimations = !1, this.values = /* @__PURE__ */ new Map(), this.KeyframeResolver = lh, this.features = {}, this.valueSubscriptions = /* @__PURE__ */ new Map(), this.prevMotionValues = {}, this.hasBeenMounted = !1, this.events = {}, this.propEventSubscriptions = {}, this.notifyUpdate = () => this.notify("Update", this.latestValues), this.render = () => {
      this.current && (this.triggerBuild(), this.renderInstance(this.current, this.renderState, this.props.style, this.projection));
    }, this.renderScheduledAt = 0, this.scheduleRender = () => {
      const V = be.now();
      this.renderScheduledAt < V && (this.renderScheduledAt = V, Vt.render(this.render, !1, !0));
    };
    const { latestValues: b, renderState: g } = y;
    this.latestValues = b, this.baseTarget = { ...b }, this.initialValues = r.initial ? { ...b } : {}, this.renderState = g, this.parent = l, this.props = r, this.presenceContext = o, this.depth = l ? l.depth + 1 : 0, this.reducedMotionConfig = c, this.skipAnimationsConfig = d, this.options = v, this.blockInitialAnimation = !!h, this.isControllingVariants = fo(r), this.isVariantNode = Sv(r), this.isVariantNode && (this.variantChildren = /* @__PURE__ */ new Set()), this.manuallyAnimateOnMount = !!(l && l.current);
    const { willChange: p, ...T } = this.scrapeMotionValuesFromProps(r, {}, this);
    for (const V in T) {
      const z = T[V];
      b[V] !== void 0 && he(z) && z.set(b[V]);
    }
  }
  mount(l) {
    if (this.hasBeenMounted)
      for (const r in this.initialValues)
        this.values.get(r)?.jump(this.initialValues[r]), this.latestValues[r] = this.initialValues[r];
    this.current = l, q2.set(l, this), this.projection && !this.projection.instance && this.projection.mount(l), this.parent && this.isVariantNode && !this.isControllingVariants && (this.removeFromVariantTree = this.parent.addVariantChild(this)), this.values.forEach((r, o) => this.bindToMotionValue(o, r)), this.reducedMotionConfig === "never" ? this.shouldReduceMotion = !1 : this.reducedMotionConfig === "always" ? this.shouldReduceMotion = !0 : (ph.current || Tv(), this.shouldReduceMotion = no.current), this.shouldSkipAnimations = this.skipAnimationsConfig ?? !1, this.parent?.addChild(this), this.update(this.props, this.presenceContext), this.hasBeenMounted = !0;
  }
  unmount() {
    this.projection && this.projection.unmount(), va(this.notifyUpdate), va(this.render), this.valueSubscriptions.forEach((l) => l()), this.valueSubscriptions.clear(), this.removeFromVariantTree && this.removeFromVariantTree(), this.parent?.removeChild(this);
    for (const l in this.events)
      this.events[l].clear();
    for (const l in this.features) {
      const r = this.features[l];
      r && (r.unmount(), r.isMounted = !1);
    }
    this.current = null;
  }
  addChild(l) {
    this.children.add(l), this.enteringChildren ?? (this.enteringChildren = /* @__PURE__ */ new Set()), this.enteringChildren.add(l);
  }
  removeChild(l) {
    this.children.delete(l), this.enteringChildren && this.enteringChildren.delete(l);
  }
  bindToMotionValue(l, r) {
    if (this.valueSubscriptions.has(l) && this.valueSubscriptions.get(l)(), r.accelerate && av.has(l) && this.current instanceof HTMLElement) {
      const { factory: h, keyframes: y, times: v, ease: b, duration: g } = r.accelerate, p = new ev({
        element: this.current,
        name: l,
        keyframes: y,
        times: v,
        ease: b,
        duration: /* @__PURE__ */ He(g)
      }), T = h(p);
      this.valueSubscriptions.set(l, () => {
        T(), p.cancel();
      });
      return;
    }
    const o = Wi.has(l);
    o && this.onBindTransform && this.onBindTransform();
    const c = r.on("change", (h) => {
      this.latestValues[l] = h, this.props.onUpdate && Vt.preRender(this.notifyUpdate), o && this.projection && (this.projection.isTransformDirty = !0), this.scheduleRender();
    });
    let d;
    typeof window < "u" && window.MotionCheckAppearSync && (d = window.MotionCheckAppearSync(this, l, r)), this.valueSubscriptions.set(l, () => {
      c(), d && d();
    });
  }
  sortNodePosition(l) {
    return !this.current || !this.sortInstanceNodePosition || this.type !== l.type ? 0 : this.sortInstanceNodePosition(this.current, l.current);
  }
  updateFeatures() {
    let l = "animation";
    for (l in ao) {
      const r = ao[l];
      if (!r)
        continue;
      const { isEnabled: o, Feature: c } = r;
      if (!this.features[l] && c && o(this.props) && (this.features[l] = new c(this)), this.features[l]) {
        const d = this.features[l];
        d.isMounted ? d.update() : (d.mount(), d.isMounted = !0);
      }
    }
  }
  triggerBuild() {
    this.build(this.renderState, this.latestValues, this.props);
  }
  /**
   * Measure the current viewport box with or without transforms.
   * Only measures axis-aligned boxes, rotate and skew must be manually
   * removed with a re-render to work.
   */
  measureViewportBox() {
    return this.current ? this.measureInstanceViewportBox(this.current, this.props) : Ft();
  }
  getStaticValue(l) {
    return this.latestValues[l];
  }
  setStaticValue(l, r) {
    this.latestValues[l] = r;
  }
  /**
   * Update the provided props. Ensure any newly-added motion values are
   * added to our map, old ones removed, and listeners updated.
   */
  update(l, r) {
    (l.transformTemplate || this.props.transformTemplate) && this.scheduleRender(), this.prevProps = this.props, this.props = l, this.prevPresenceContext = this.presenceContext, this.presenceContext = r;
    for (let o = 0; o < A0.length; o++) {
      const c = A0[o];
      this.propEventSubscriptions[c] && (this.propEventSubscriptions[c](), delete this.propEventSubscriptions[c]);
      const d = "on" + c, h = l[d];
      h && (this.propEventSubscriptions[c] = this.on(c, h));
    }
    this.prevMotionValues = G2(this, this.scrapeMotionValuesFromProps(l, this.prevProps || {}, this), this.prevMotionValues), this.handleChildMotionValue && this.handleChildMotionValue();
  }
  getProps() {
    return this.props;
  }
  /**
   * Returns the variant definition with a given name.
   */
  getVariant(l) {
    return this.props.variants ? this.props.variants[l] : void 0;
  }
  /**
   * Returns the defined default transition on this component.
   */
  getDefaultTransition() {
    return this.props.transition;
  }
  getTransformPagePoint() {
    return this.props.transformPagePoint;
  }
  getClosestVariantNode() {
    return this.isVariantNode ? this : this.parent ? this.parent.getClosestVariantNode() : void 0;
  }
  /**
   * Add a child visual element to our set of children.
   */
  addVariantChild(l) {
    const r = this.getClosestVariantNode();
    if (r)
      return r.variantChildren && r.variantChildren.add(l), () => r.variantChildren.delete(l);
  }
  /**
   * Add a motion value and bind it to this visual element.
   */
  addValue(l, r) {
    const o = this.values.get(l);
    r !== o && (o && this.removeValue(l), this.bindToMotionValue(l, r), this.values.set(l, r), this.latestValues[l] = r.get());
  }
  /**
   * Remove a motion value and unbind any active subscriptions.
   */
  removeValue(l) {
    this.values.delete(l);
    const r = this.valueSubscriptions.get(l);
    r && (r(), this.valueSubscriptions.delete(l)), delete this.latestValues[l], this.removeValueFromRenderState(l, this.renderState);
  }
  /**
   * Check whether we have a motion value for this key
   */
  hasValue(l) {
    return this.values.has(l);
  }
  getValue(l, r) {
    if (this.props.values && this.props.values[l])
      return this.props.values[l];
    let o = this.values.get(l);
    return o === void 0 && r !== void 0 && (o = ki(r === null ? void 0 : r, { owner: this }), this.addValue(l, o)), o;
  }
  /**
   * If we're trying to animate to a previously unencountered value,
   * we need to check for it in our state and as a last resort read it
   * directly from the instance (which might have performance implications).
   */
  readValue(l, r) {
    let o = this.latestValues[l] !== void 0 || !this.current ? this.latestValues[l] : this.getBaseTargetFromProps(this.props, l) ?? this.readValueFromInstance(this.current, l, this.options);
    return o != null && (typeof o == "string" && (Tg(o) || Eg(o)) ? o = parseFloat(o) : !Y2(o) && sn.test(r) && (o = mv(l, r)), this.setBaseTarget(l, he(o) ? o.get() : o)), he(o) ? o.get() : o;
  }
  /**
   * Set the base target to later animate back to. This is currently
   * only hydrated on creation and when we first read a value.
   */
  setBaseTarget(l, r) {
    this.baseTarget[l] = r;
  }
  /**
   * Find the base target for a value thats been removed from all animation
   * props.
   */
  getBaseTarget(l) {
    const { initial: r } = this.props;
    let o;
    if (typeof r == "string" || typeof r == "object") {
      const d = oh(this.props, r, this.presenceContext?.custom);
      d && (o = d[l]);
    }
    if (r && o !== void 0)
      return o;
    const c = this.getBaseTargetFromProps(this.props, l);
    return c !== void 0 && !he(c) ? c : this.initialValues[l] !== void 0 && o === void 0 ? void 0 : this.baseTarget[l];
  }
  on(l, r) {
    return this.events[l] || (this.events[l] = new Ff()), this.events[l].add(r);
  }
  notify(l, ...r) {
    this.events[l] && this.events[l].notify(...r);
  }
  scheduleRenderMicrotask() {
    fh.render(this.render);
  }
}
class Ev extends Z2 {
  constructor() {
    super(...arguments), this.KeyframeResolver = b2;
  }
  sortInstanceNodePosition(l, r) {
    return l.compareDocumentPosition(r) & 2 ? 1 : -1;
  }
  getBaseTargetFromProps(l, r) {
    const o = l.style;
    return o ? o[r] : void 0;
  }
  removeValueFromRenderState(l, { vars: r, style: o }) {
    delete r[l], delete o[l];
  }
  handleChildMotionValue() {
    this.childSubscription && (this.childSubscription(), delete this.childSubscription);
    const { children: l } = this.props;
    he(l) && (this.childSubscription = l.on("change", (r) => {
      this.current && (this.current.textContent = `${r}`);
    }));
  }
}
class ba {
  constructor(l) {
    this.isMounted = !1, this.node = l;
  }
  update() {
  }
}
function Av({ top: i, left: l, right: r, bottom: o }) {
  return {
    x: { min: l, max: r },
    y: { min: i, max: o }
  };
}
function K2({ x: i, y: l }) {
  return { top: l.min, right: i.max, bottom: l.max, left: i.min };
}
function J2(i, l) {
  if (!l)
    return i;
  const r = l({ x: i.left, y: i.top }), o = l({ x: i.right, y: i.bottom });
  return {
    top: r.y,
    left: r.x,
    bottom: o.y,
    right: o.x
  };
}
function rf(i) {
  return i === void 0 || i === 1;
}
function Hf({ scale: i, scaleX: l, scaleY: r }) {
  return !rf(i) || !rf(l) || !rf(r);
}
function Ka(i) {
  return Hf(i) || Mv(i) || i.z || i.rotate || i.rotateX || i.rotateY || i.skewX || i.skewY;
}
function Mv(i) {
  return M0(i.x) || M0(i.y);
}
function M0(i) {
  return i && i !== "0%";
}
function io(i, l, r) {
  const o = i - r, c = l * o;
  return r + c;
}
function D0(i, l, r, o, c) {
  return c !== void 0 && (i = io(i, c, o)), io(i, r, o) + l;
}
function Lf(i, l = 0, r = 1, o, c) {
  i.min = D0(i.min, l, r, o, c), i.max = D0(i.max, l, r, o, c);
}
function Dv(i, { x: l, y: r }) {
  Lf(i.x, l.translate, l.scale, l.originPoint), Lf(i.y, r.translate, r.scale, r.originPoint);
}
const C0 = 0.999999999999, O0 = 1.0000000000001;
function k2(i, l, r, o = !1) {
  const c = r.length;
  if (!c)
    return;
  l.x = l.y = 1;
  let d, h;
  for (let y = 0; y < c; y++) {
    d = r[y], h = d.projectionDelta;
    const { visualElement: v } = d.options;
    v && v.props.style && v.props.style.display === "contents" || (o && d.options.layoutScroll && d.scroll && d !== d.root && (Tn(i.x, -d.scroll.offset.x), Tn(i.y, -d.scroll.offset.y)), h && (l.x *= h.x.scale, l.y *= h.y.scale, Dv(i, h)), o && Ka(d.latestValues) && Ju(i, d.latestValues, d.layout?.layoutBox));
  }
  l.x < O0 && l.x > C0 && (l.x = 1), l.y < O0 && l.y > C0 && (l.y = 1);
}
function Tn(i, l) {
  i.min += l, i.max += l;
}
function N0(i, l, r, o, c = 0.5) {
  const d = wt(i.min, i.max, c);
  Lf(i, l, r, d, o);
}
function z0(i, l) {
  return typeof i == "string" ? parseFloat(i) / 100 * (l.max - l.min) : i;
}
function Ju(i, l, r) {
  const o = r ?? i;
  N0(i.x, z0(l.x, o.x), l.scaleX, l.scale, l.originX), N0(i.y, z0(l.y, o.y), l.scaleY, l.scale, l.originY);
}
function Cv(i, l) {
  return Av(J2(i.getBoundingClientRect(), l));
}
function P2(i, l, r) {
  const o = Cv(i, r), { scroll: c } = l;
  return c && (Tn(o.x, c.offset.x), Tn(o.y, c.offset.y)), o;
}
const F2 = {
  x: "translateX",
  y: "translateY",
  z: "translateZ",
  transformPerspective: "perspective"
}, W2 = Fi.length;
function I2(i, l, r) {
  let o = "", c = !0;
  for (let h = 0; h < W2; h++) {
    const y = Fi[h], v = i[y];
    if (v === void 0)
      continue;
    let b = !0;
    if (typeof v == "number")
      b = v === (y.startsWith("scale") ? 1 : 0);
    else {
      const g = parseFloat(v);
      b = y.startsWith("scale") ? g === 1 : g === 0;
    }
    if (!b || r) {
      const g = Bf(v, eo[y]);
      if (!b) {
        c = !1;
        const p = F2[y] || y;
        o += `${p}(${g}) `;
      }
      r && (l[y] = g);
    }
  }
  const d = i.pathRotation;
  return d && (c = !1, o += `rotate(${Bf(d, eo.pathRotation)}) `), o = o.trim(), r ? o = r(l, c ? "" : o) : c && (o = "none"), o;
}
function gh(i, l, r) {
  const { style: o, vars: c, transformOrigin: d } = i;
  let h = !1, y = !1;
  for (const v in l) {
    const b = l[v];
    if (Wi.has(v)) {
      h = !0;
      continue;
    } else if (Hg(v)) {
      c[v] = b;
      continue;
    } else {
      const g = Bf(b, eo[v]);
      v.startsWith("origin") ? (y = !0, d[v] = g) : o[v] = g;
    }
  }
  if (l.transform || (h || r ? o.transform = I2(l, i.transform, r) : o.transform && (o.transform = "none")), y) {
    const { originX: v = "50%", originY: b = "50%", originZ: g = 0 } = d;
    o.transformOrigin = `${v} ${b} ${g}`;
  }
}
function Ov(i, { style: l, vars: r }, o, c) {
  const d = i.style;
  let h;
  for (h in l)
    d[h] = l[h];
  c?.applyProjectionStyles(d, o);
  for (h in r)
    d.setProperty(h, r[h]);
}
function R0(i, l) {
  return l.max === l.min ? 0 : i / (l.max - l.min) * 100;
}
const kl = {
  correct: (i, l) => {
    if (!l.target)
      return i;
    if (typeof i == "string")
      if (F.test(i))
        i = parseFloat(i);
      else
        return i;
    const r = R0(i, l.target.x), o = R0(i, l.target.y);
    return `${r}% ${o}%`;
  }
}, $2 = {
  correct: (i, { treeScale: l, projectionDelta: r }) => {
    const o = i, c = sn.parse(i);
    if (c.length > 5)
      return o;
    const d = sn.createTransformer(i), h = typeof c[0] != "number" ? 1 : 0, y = r.x.scale * l.x, v = r.y.scale * l.y;
    c[0 + h] /= y, c[1 + h] /= v;
    const b = wt(y, v, 0.5);
    return typeof c[2 + h] == "number" && (c[2 + h] /= b), typeof c[3 + h] == "number" && (c[3 + h] /= b), d(c);
  }
}, Yf = {
  borderRadius: {
    ...kl,
    applyTo: [...ch]
  },
  borderTopLeftRadius: kl,
  borderTopRightRadius: kl,
  borderBottomLeftRadius: kl,
  borderBottomRightRadius: kl,
  boxShadow: $2
};
function Nv(i, { layout: l, layoutId: r }) {
  return Wi.has(i) || i.startsWith("origin") || (l || r !== void 0) && (!!Yf[i] || i === "opacity");
}
function vh(i, l, r) {
  const o = i.style, c = l?.style, d = {};
  if (!o)
    return d;
  for (const h in o)
    (he(o[h]) || c && he(c[h]) || Nv(h, i) || r?.getValue(h)?.liveStyle !== void 0) && (d[h] = o[h]);
  return d;
}
function tE(i) {
  return window.getComputedStyle(i);
}
class eE extends Ev {
  constructor() {
    super(...arguments), this.type = "html", this.renderInstance = Ov;
  }
  mount(l) {
    oo(!!l.style), super.mount(l);
  }
  readValueFromInstance(l, r) {
    if (Wi.has(r))
      return this.projection?.isProjecting ? Df(r) : Tx(l, r);
    {
      const o = tE(l), c = (Hg(r) ? o.getPropertyValue(r) : o[r]) || 0;
      return typeof c == "string" ? c.trim() : c;
    }
  }
  measureInstanceViewportBox(l, { transformPagePoint: r }) {
    return Cv(l, r);
  }
  build(l, r, o) {
    gh(l, r, o.transformTemplate);
  }
  scrapeMotionValuesFromProps(l, r, o) {
    return vh(l, r, o);
  }
}
const nE = {
  offset: "stroke-dashoffset",
  array: "stroke-dasharray"
}, aE = {
  offset: "strokeDashoffset",
  array: "strokeDasharray"
};
function iE(i, l, r = 1, o = 0, c = !0) {
  i.pathLength = 1;
  const d = c ? nE : aE;
  i[d.offset] = `${-o}`, i[d.array] = `${l} ${r}`;
}
const lE = [
  "offsetDistance",
  "offsetPath",
  "offsetRotate",
  "offsetAnchor"
];
function zv(i, {
  attrX: l,
  attrY: r,
  attrScale: o,
  pathLength: c,
  pathSpacing: d = 1,
  pathOffset: h = 0,
  // This is object creation, which we try to avoid per-frame.
  ...y
}, v, b, g) {
  if (gh(i, y, b), v) {
    i.style.viewBox && (i.attrs.viewBox = i.style.viewBox);
    return;
  }
  i.attrs = i.style, i.style = {};
  const { attrs: p, style: T } = i;
  p.transform && (T.transform = p.transform, delete p.transform), (T.transform || p.transformOrigin) && (T.transformOrigin = p.transformOrigin ?? "50% 50%", delete p.transformOrigin), T.transform && (T.transformBox = g?.transformBox ?? "fill-box", delete p.transformBox);
  for (const V of lE)
    p[V] !== void 0 && (T[V] = p[V], delete p[V]);
  l !== void 0 && (p.x = l), r !== void 0 && (p.y = r), o !== void 0 && (p.scale = o), c !== void 0 && iE(p, c, d, h, !1);
}
const Rv = /* @__PURE__ */ new Set([
  "baseFrequency",
  "diffuseConstant",
  "kernelMatrix",
  "kernelUnitLength",
  "keySplines",
  "keyTimes",
  "limitingConeAngle",
  "markerHeight",
  "markerWidth",
  "numOctaves",
  "targetX",
  "targetY",
  "surfaceScale",
  "specularConstant",
  "specularExponent",
  "stdDeviation",
  "tableValues",
  "viewBox",
  "gradientTransform",
  "pathLength",
  "startOffset",
  "textLength",
  "lengthAdjust"
]), _v = (i) => typeof i == "string" && i.toLowerCase() === "svg";
function sE(i, l, r, o) {
  Ov(i, l, void 0, o);
  for (const c in l.attrs)
    i.setAttribute(Rv.has(c) ? c : rh(c), l.attrs[c]);
}
function wv(i, l, r) {
  const o = vh(i, l, r);
  for (const c in i)
    if (he(i[c]) || he(l[c])) {
      const d = Fi.indexOf(c) !== -1 ? "attr" + c.charAt(0).toUpperCase() + c.substring(1) : c;
      o[d] = i[c];
    }
  return o;
}
class uE extends Ev {
  constructor() {
    super(...arguments), this.type = "svg", this.isSVGTag = !1, this.measureInstanceViewportBox = Ft;
  }
  getBaseTargetFromProps(l, r) {
    return l[r];
  }
  readValueFromInstance(l, r) {
    if (Wi.has(r)) {
      const o = dv(r);
      return o && o.default || 0;
    }
    return r = Rv.has(r) ? r : rh(r), l.getAttribute(r);
  }
  scrapeMotionValuesFromProps(l, r, o) {
    return wv(l, r, o);
  }
  build(l, r, o) {
    zv(l, r, this.isSVGTag, o.transformTemplate, o.style);
  }
  renderInstance(l, r, o, c) {
    sE(l, r, o, c);
  }
  mount(l) {
    this.isSVGTag = _v(l.tagName), super.mount(l);
  }
}
const oE = yh.length;
function Vv(i) {
  if (!i)
    return;
  if (!i.isControllingVariants) {
    const r = i.parent ? Vv(i.parent) || {} : {};
    return i.props.initial !== void 0 && (r.initial = i.props.initial), r;
  }
  const l = {};
  for (let r = 0; r < oE; r++) {
    const o = yh[r], c = i.props[o];
    (ns(c) || c === !1) && (l[o] = c);
  }
  return l;
}
function jv(i, l) {
  if (!Array.isArray(l))
    return !1;
  const r = l.length;
  if (r !== i.length)
    return !1;
  for (let o = 0; o < r; o++)
    if (l[o] !== i[o])
      return !1;
  return !0;
}
const rE = [...mh].reverse(), cE = mh.length;
function fE(i) {
  return (l) => Promise.all(l.map(({ animation: r, options: o }) => o2(i, r, o)));
}
function hE(i) {
  let l = fE(i), r = _0(), o = !0, c = !1;
  const d = (b) => (g, p) => {
    const T = Wa(i, p, b === "exit" ? i.presenceContext?.custom : void 0);
    if (T) {
      const { transition: V, transitionEnd: z, ...B } = T;
      g = { ...g, ...B, ...z };
    }
    return g;
  };
  function h(b) {
    l = b(i);
  }
  function y(b) {
    const { props: g } = i, p = Vv(i.parent) || {}, T = [], V = /* @__PURE__ */ new Set();
    let z = {}, B = 1 / 0;
    for (let L = 0; L < cE; L++) {
      const Y = rE[L], U = r[Y], G = g[Y] !== void 0 ? g[Y] : p[Y], nt = ns(G), rt = Y === b ? U.isActive : null;
      rt === !1 && (B = L);
      let J = G === p[Y] && G !== g[Y] && nt;
      if (J && (o || c) && i.manuallyAnimateOnMount && (J = !1), U.protectedKeys = { ...z }, // If it isn't active and hasn't *just* been set as inactive
      !U.isActive && rt === null || // If we didn't and don't have any defined prop for this animation type
      !G && !U.prevProp || // Or if the prop doesn't define an animation
      co(G) || typeof G == "boolean")
        continue;
      if (Y === "exit" && U.isActive && rt !== !0) {
        U.prevResolvedValues && (z = {
          ...z,
          ...U.prevResolvedValues
        });
        continue;
      }
      const Q = dE(U.prevProp, G);
      let Ot = Q || // If we're making this variant active, we want to always make it active
      Y === b && U.isActive && !J && nt || // If we removed a higher-priority variant (i is in reverse order)
      L > B && nt, $ = !1;
      const vt = Array.isArray(G) ? G : [G];
      let Nt = vt.reduce(d(Y), {});
      rt === !1 && (Nt = {});
      const { prevResolvedValues: de = {} } = U, Wt = {
        ...de,
        ...Nt
      }, zt = (k) => {
        Ot = !0, V.has(k) && ($ = !0, V.delete(k)), U.needsAnimating[k] = !0;
        const ct = i.getValue(k);
        ct && (ct.liveStyle = !1);
      };
      for (const k in Wt) {
        const ct = Nt[k], ht = de[k];
        if (z.hasOwnProperty(k))
          continue;
        let It = !1;
        _f(ct) && _f(ht) ? It = !jv(ct, ht) || Q : It = ct !== ht, It ? ct != null ? zt(k) : V.add(k) : ct !== void 0 && V.has(k) ? zt(k) : U.protectedKeys[k] = !0;
      }
      U.prevProp = G, U.prevResolvedValues = Nt, U.isActive && (z = { ...z, ...Nt }), (o || c) && i.blockInitialAnimation && (Ot = !1);
      const q = J && Q;
      Ot && (!q || $) && T.push(...vt.map((k) => {
        const ct = { type: Y };
        if (typeof k == "string" && (o || c) && !q && i.manuallyAnimateOnMount && i.parent) {
          const { parent: ht } = i, It = Wa(ht, k);
          if (ht.enteringChildren && It) {
            const { delayChildren: Fe } = It.transition || {};
            ct.delay = iv(ht.enteringChildren, i, Fe);
          }
        }
        return {
          animation: k,
          options: ct
        };
      }));
    }
    if (V.size) {
      const L = {};
      if (typeof g.initial != "boolean") {
        const Y = Wa(i, Array.isArray(g.initial) ? g.initial[0] : g.initial);
        Y && Y.transition && (L.transition = Y.transition);
      }
      V.forEach((Y) => {
        const U = i.getBaseTarget(Y), G = i.getValue(Y);
        G && (G.liveStyle = !0), L[Y] = U ?? null;
      }), T.push({ animation: L });
    }
    let j = !!T.length;
    return o && (g.initial === !1 || g.initial === g.animate) && !i.manuallyAnimateOnMount && (j = !1), o = !1, c = !1, j ? l(T) : Promise.resolve();
  }
  function v(b, g) {
    if (r[b].isActive === g)
      return Promise.resolve();
    i.variantChildren?.forEach((T) => T.animationState?.setActive(b, g)), r[b].isActive = g;
    const p = y(b);
    for (const T in r)
      r[T].protectedKeys = {};
    return p;
  }
  return {
    animateChanges: y,
    setActive: v,
    setAnimateFunction: h,
    getState: () => r,
    reset: () => {
      r = _0(), c = !0;
    }
  };
}
function dE(i, l) {
  return typeof l == "string" ? l !== i : Array.isArray(l) ? !jv(l, i) : !1;
}
function Za(i = !1) {
  return {
    isActive: i,
    protectedKeys: {},
    needsAnimating: {},
    prevResolvedValues: {}
  };
}
function _0() {
  return {
    animate: Za(!0),
    whileInView: Za(),
    whileHover: Za(),
    whileTap: Za(),
    whileDrag: Za(),
    whileFocus: Za(),
    exit: Za()
  };
}
function qf(i, l) {
  i.min = l.min, i.max = l.max;
}
function an(i, l) {
  qf(i.x, l.x), qf(i.y, l.y);
}
function w0(i, l) {
  i.translate = l.translate, i.scale = l.scale, i.originPoint = l.originPoint, i.origin = l.origin;
}
const Uv = 1e-4, mE = 1 - Uv, yE = 1 + Uv, Bv = 0.01, pE = 0 - Bv, gE = 0 + Bv;
function Se(i) {
  return i.max - i.min;
}
function vE(i, l, r) {
  return Math.abs(i - l) <= r;
}
function V0(i, l, r, o = 0.5) {
  i.origin = o, i.originPoint = wt(l.min, l.max, i.origin), i.scale = Se(r) / Se(l), i.translate = wt(r.min, r.max, i.origin) - i.originPoint, (i.scale >= mE && i.scale <= yE || isNaN(i.scale)) && (i.scale = 1), (i.translate >= pE && i.translate <= gE || isNaN(i.translate)) && (i.translate = 0);
}
function Il(i, l, r, o) {
  V0(i.x, l.x, r.x, o ? o.originX : void 0), V0(i.y, l.y, r.y, o ? o.originY : void 0);
}
function j0(i, l, r, o = 0) {
  const c = o ? wt(r.min, r.max, o) : r.min;
  i.min = c + l.min, i.max = i.min + Se(l);
}
function bE(i, l, r, o) {
  j0(i.x, l.x, r.x, o?.x), j0(i.y, l.y, r.y, o?.y);
}
function U0(i, l, r, o = 0) {
  const c = o ? wt(r.min, r.max, o) : r.min;
  i.min = l.min - c, i.max = i.min + Se(l);
}
function lo(i, l, r, o) {
  U0(i.x, l.x, r.x, o?.x), U0(i.y, l.y, r.y, o?.y);
}
function B0(i, l, r, o, c) {
  return i -= l, i = io(i, 1 / r, o), c !== void 0 && (i = io(i, 1 / c, o)), i;
}
function SE(i, l = 0, r = 1, o = 0.5, c, d = i, h = i) {
  if (xn.test(l) && (l = parseFloat(l), l = wt(h.min, h.max, l / 100) - h.min), typeof l != "number")
    return;
  let y = wt(d.min, d.max, o);
  i === d && (y -= l), i.min = B0(i.min, l, r, y, c), i.max = B0(i.max, l, r, y, c);
}
function H0(i, l, [r, o, c], d, h) {
  SE(i, l[r], l[o], l[c], l.scale, d, h);
}
const TE = ["x", "scaleX", "originX"], xE = ["y", "scaleY", "originY"];
function L0(i, l, r, o) {
  H0(i.x, l, TE, r ? r.x : void 0, o ? o.x : void 0), H0(i.y, l, xE, r ? r.y : void 0, o ? o.y : void 0);
}
function Y0(i) {
  return i.translate === 0 && i.scale === 1;
}
function Hv(i) {
  return Y0(i.x) && Y0(i.y);
}
function q0(i, l) {
  return i.min === l.min && i.max === l.max;
}
function EE(i, l) {
  return q0(i.x, l.x) && q0(i.y, l.y);
}
function G0(i, l) {
  return Math.round(i.min) === Math.round(l.min) && Math.round(i.max) === Math.round(l.max);
}
function Lv(i, l) {
  return G0(i.x, l.x) && G0(i.y, l.y);
}
function X0(i) {
  return Se(i.x) / Se(i.y);
}
function Q0(i, l) {
  return i.translate === l.translate && i.scale === l.scale && i.originPoint === l.originPoint;
}
function Sn(i) {
  return [i("x"), i("y")];
}
function AE(i, l, r) {
  let o = "";
  const c = i.x.translate / l.x, d = i.y.translate / l.y, h = r?.z || 0;
  if ((c || d || h) && (o = `translate3d(${c}px, ${d}px, ${h}px) `), (l.x !== 1 || l.y !== 1) && (o += `scale(${1 / l.x}, ${1 / l.y}) `), r) {
    const { transformPerspective: b, rotate: g, pathRotation: p, rotateX: T, rotateY: V, skewX: z, skewY: B } = r;
    b && (o = `perspective(${b}px) ${o}`), g && (o += `rotate(${g}deg) `), p && (o += `rotate(${p}deg) `), T && (o += `rotateX(${T}deg) `), V && (o += `rotateY(${V}deg) `), z && (o += `skewX(${z}deg) `), B && (o += `skewY(${B}deg) `);
  }
  const y = i.x.scale * l.x, v = i.y.scale * l.y;
  return (y !== 1 || v !== 1) && (o += `scale(${y}, ${v})`), o || "none";
}
const ME = ch.length, Z0 = (i) => typeof i == "string" ? parseFloat(i) : i, K0 = (i) => typeof i == "number" || F.test(i);
function DE(i, l, r, o, c, d) {
  c ? (i.opacity = wt(0, r.opacity ?? 1, CE(o)), i.opacityExit = wt(l.opacity ?? 1, 0, OE(o))) : d && (i.opacity = wt(l.opacity ?? 1, r.opacity ?? 1, o));
  for (let h = 0; h < ME; h++) {
    const y = ch[h];
    let v = J0(l, y), b = J0(r, y);
    if (v === void 0 && b === void 0)
      continue;
    v || (v = 0), b || (b = 0), v === 0 || b === 0 || K0(v) === K0(b) ? (i[y] = Math.max(wt(Z0(v), Z0(b), o), 0), (xn.test(b) || xn.test(v)) && (i[y] += "%")) : i[y] = b;
  }
  (l.rotate || r.rotate) && (i.rotate = wt(l.rotate || 0, r.rotate || 0, o));
}
function J0(i, l) {
  return i[l] !== void 0 ? i[l] : i.borderRadius;
}
const CE = /* @__PURE__ */ Yv(0, 0.5, _g), OE = /* @__PURE__ */ Yv(0.5, 0.95, Pe);
function Yv(i, l, r) {
  return (o) => o < i ? 0 : o > l ? 1 : r(/* @__PURE__ */ ts(i, l, o));
}
function NE(i, l, r) {
  const o = he(i) ? i : ki(i);
  return o.start(uh("", o, l, r)), o.animation;
}
function as(i, l, r, o = { passive: !0 }) {
  return i.addEventListener(l, r, o), () => i.removeEventListener(l, r, o);
}
const zE = (i, l) => i.depth - l.depth;
class RE {
  constructor() {
    this.children = [], this.isDirty = !1;
  }
  add(l) {
    Pf(this.children, l), this.isDirty = !0;
  }
  remove(l) {
    Fu(this.children, l), this.isDirty = !0;
  }
  forEach(l) {
    this.isDirty && this.children.sort(zE), this.isDirty = !1, this.children.forEach(l);
  }
}
function _E(i, l) {
  const r = be.now(), o = ({ timestamp: c }) => {
    const d = c - r;
    d >= l && (va(o), i(d - l));
  };
  return Vt.setup(o, !0), () => va(o);
}
function ku(i) {
  return he(i) ? i.get() : i;
}
class wE {
  constructor() {
    this.members = [];
  }
  add(l) {
    Pf(this.members, l);
    for (let r = this.members.length - 1; r >= 0; r--) {
      const o = this.members[r];
      if (o === l || o === this.lead || o === this.prevLead)
        continue;
      const c = o.instance;
      (!c || c.isConnected === !1) && !o.snapshot && (Fu(this.members, o), o.unmount());
    }
    l.scheduleRender();
  }
  remove(l) {
    if (Fu(this.members, l), l === this.prevLead && (this.prevLead = void 0), l === this.lead) {
      const r = this.members[this.members.length - 1];
      r && this.promote(r);
    }
  }
  relegate(l) {
    for (let r = this.members.indexOf(l) - 1; r >= 0; r--) {
      const o = this.members[r];
      if (o.isPresent !== !1 && o.instance?.isConnected !== !1)
        return this.promote(o), !0;
    }
    return !1;
  }
  promote(l, r) {
    const o = this.lead;
    if (l !== o && (this.prevLead = o, this.lead = l, l.show(), o)) {
      o.updateSnapshot(), l.scheduleRender();
      const { layoutDependency: c } = o.options, { layoutDependency: d } = l.options;
      (c === void 0 || c !== d) && (l.resumeFrom = o, r && (o.preserveOpacity = !0), o.snapshot && (l.snapshot = o.snapshot, l.snapshot.latestValues = o.animationValues || o.latestValues), l.root?.isUpdating && (l.isLayoutDirty = !0)), l.options.crossfade === !1 && o.hide();
    }
  }
  exitAnimationComplete() {
    this.members.forEach((l) => {
      l.options.onExitComplete?.(), l.resumingFrom?.options.onExitComplete?.();
    });
  }
  scheduleRender() {
    this.members.forEach((l) => l.instance && l.scheduleRender(!1));
  }
  removeLeadSnapshot() {
    this.lead?.snapshot && (this.lead.snapshot = void 0);
  }
}
const Pu = {
  /**
   * Global flag as to whether the tree has animated since the last time
   * we resized the window
   */
  hasAnimatedSinceResize: !0,
  /**
   * We set this to true once, on the first update. Any nodes added to the tree beyond that
   * update will be given a `data-projection-id` attribute.
   */
  hasEverUpdated: !1
}, cf = ["", "X", "Y", "Z"], VE = 1e3;
let jE = 0;
function ff(i, l, r, o) {
  const { latestValues: c } = l;
  c[i] && (r[i] = c[i], l.setStaticValue(i, 0), o && (o[i] = 0));
}
function qv(i) {
  if (i.hasCheckedOptimisedAppear = !0, i.root === i)
    return;
  const { visualElement: l } = i.options;
  if (!l)
    return;
  const r = rv(l);
  if (window.MotionHasOptimisedAnimation(r, "transform")) {
    const { layout: c, layoutId: d } = i.options;
    window.MotionCancelOptimisedAnimation(r, "transform", Vt, !(c || d));
  }
  const { parent: o } = i;
  o && !o.hasCheckedOptimisedAppear && qv(o);
}
function Gv({ attachResizeListener: i, defaultParent: l, measureScroll: r, checkIsScrollRoot: o, resetTransform: c }) {
  return class {
    constructor(h = {}, y = l?.()) {
      this.id = jE++, this.animationId = 0, this.animationCommitId = 0, this.children = /* @__PURE__ */ new Set(), this.options = {}, this.isTreeAnimating = !1, this.isAnimationBlocked = !1, this.isLayoutDirty = !1, this.isProjectionDirty = !1, this.isSharedProjectionDirty = !1, this.isTransformDirty = !1, this.updateManuallyBlocked = !1, this.updateBlockedByResize = !1, this.isUpdating = !1, this.isSVG = !1, this.needsReset = !1, this.shouldResetTransform = !1, this.hasCheckedOptimisedAppear = !1, this.treeScale = { x: 1, y: 1 }, this.eventHandlers = /* @__PURE__ */ new Map(), this.hasTreeAnimated = !1, this.layoutVersion = 0, this.updateScheduled = !1, this.scheduleUpdate = () => this.update(), this.projectionUpdateScheduled = !1, this.checkUpdateFailed = () => {
        this.isUpdating && (this.isUpdating = !1, this.clearAllSnapshots());
      }, this.updateProjection = () => {
        this.projectionUpdateScheduled = !1, this.nodes.forEach(HE), this.nodes.forEach(QE), this.nodes.forEach(ZE), this.nodes.forEach(LE);
      }, this.resolvedRelativeTargetAt = 0, this.linkedParentVersion = 0, this.hasProjected = !1, this.isVisible = !0, this.animationProgress = 0, this.sharedNodes = /* @__PURE__ */ new Map(), this.latestValues = h, this.root = y ? y.root || y : this, this.path = y ? [...y.path, y] : [], this.parent = y, this.depth = y ? y.depth + 1 : 0;
      for (let v = 0; v < this.path.length; v++)
        this.path[v].shouldResetTransform = !0;
      this.root === this && (this.nodes = new RE());
    }
    addEventListener(h, y) {
      return this.eventHandlers.has(h) || this.eventHandlers.set(h, new Ff()), this.eventHandlers.get(h).add(y);
    }
    notifyListeners(h, ...y) {
      const v = this.eventHandlers.get(h);
      v && v.notify(...y);
    }
    hasListeners(h) {
      return this.eventHandlers.has(h);
    }
    /**
     * Lifecycles
     */
    mount(h) {
      if (this.instance)
        return;
      this.isSVG = dh(h) && !H2(h), this.instance = h;
      const { layoutId: y, layout: v, visualElement: b } = this.options;
      if (b && !b.current && b.mount(h), this.root.nodes.add(this), this.parent && this.parent.children.add(this), this.root.hasTreeAnimated && (v || y) && (this.isLayoutDirty = !0), i) {
        let g, p = 0;
        const T = () => this.root.updateBlockedByResize = !1;
        Vt.read(() => {
          p = window.innerWidth;
        }), i(h, () => {
          const V = window.innerWidth;
          V !== p && (p = V, this.root.updateBlockedByResize = !0, g && g(), g = _E(T, 250), Pu.hasAnimatedSinceResize && (Pu.hasAnimatedSinceResize = !1, this.nodes.forEach(F0)));
        });
      }
      y && this.root.registerSharedNode(y, this), this.options.animate !== !1 && b && (y || v) && this.addEventListener("didUpdate", ({ delta: g, hasLayoutChanged: p, hasRelativeLayoutChanged: T, layout: V }) => {
        if (this.isTreeAnimationBlocked()) {
          this.target = void 0, this.relativeTarget = void 0;
          return;
        }
        const z = this.options.transition || b.getDefaultTransition() || FE, { onLayoutAnimationStart: B, onLayoutAnimationComplete: j } = b.getProps(), L = !this.targetLayout || !Lv(this.targetLayout, V), Y = !p && T;
        if (this.options.layoutRoot || this.resumeFrom || Y || p && (L || !this.currentAnimation)) {
          this.resumeFrom && (this.resumingFrom = this.resumeFrom, this.resumingFrom.resumingFrom = void 0);
          const U = {
            ...sh(z, "layout"),
            onPlay: B,
            onComplete: j
          };
          (b.shouldReduceMotion || this.options.layoutRoot) && (U.delay = 0, U.type = !1), this.startAnimation(U), this.setAnimationOrigin(g, Y, U.path);
        } else
          p || F0(this), this.isLead() && this.options.onExitComplete && this.options.onExitComplete();
        this.targetLayout = V;
      });
    }
    unmount() {
      this.options.layoutId && this.willUpdate(), this.root.nodes.remove(this);
      const h = this.getStack();
      h && h.remove(this), this.parent && this.parent.children.delete(this), this.instance = void 0, this.eventHandlers.clear(), va(this.updateProjection);
    }
    // only on the root
    blockUpdate() {
      this.updateManuallyBlocked = !0;
    }
    unblockUpdate() {
      this.updateManuallyBlocked = !1;
    }
    isUpdateBlocked() {
      return this.updateManuallyBlocked || this.updateBlockedByResize;
    }
    isTreeAnimationBlocked() {
      return this.isAnimationBlocked || this.parent && this.parent.isTreeAnimationBlocked() || !1;
    }
    // Note: currently only running on root node
    startUpdate() {
      this.isUpdateBlocked() || (this.isUpdating = !0, this.nodes && this.nodes.forEach(KE), this.animationId++);
    }
    getTransformTemplate() {
      const { visualElement: h } = this.options;
      return h && h.getProps().transformTemplate;
    }
    willUpdate(h = !0) {
      if (this.root.hasTreeAnimated = !0, this.root.isUpdateBlocked()) {
        this.options.onExitComplete && this.options.onExitComplete();
        return;
      }
      if (window.MotionCancelOptimisedAnimation && !this.hasCheckedOptimisedAppear && qv(this), !this.root.isUpdating && this.root.startUpdate(), this.isLayoutDirty)
        return;
      this.isLayoutDirty = !0;
      for (let g = 0; g < this.path.length; g++) {
        const p = this.path[g];
        p.shouldResetTransform = !0, (typeof p.latestValues.x == "string" || typeof p.latestValues.y == "string") && (p.isLayoutDirty = !0), p.updateScroll("snapshot"), p.options.layoutRoot && p.willUpdate(!1);
      }
      const { layoutId: y, layout: v } = this.options;
      if (y === void 0 && !v)
        return;
      const b = this.getTransformTemplate();
      this.prevTransformTemplateValue = b ? b(this.latestValues, "") : void 0, this.updateSnapshot(), h && this.notifyListeners("willUpdate");
    }
    update() {
      if (this.updateScheduled = !1, this.isUpdateBlocked()) {
        const v = this.updateBlockedByResize;
        this.unblockUpdate(), this.updateBlockedByResize = !1, this.clearAllSnapshots(), v && this.nodes.forEach(qE), this.nodes.forEach(k0);
        return;
      }
      if (this.animationId <= this.animationCommitId) {
        this.nodes.forEach(P0);
        return;
      }
      this.animationCommitId = this.animationId, this.isUpdating ? (this.isUpdating = !1, this.nodes.forEach(GE), this.nodes.forEach(XE), this.nodes.forEach(UE), this.nodes.forEach(BE)) : this.nodes.forEach(P0), this.clearAllSnapshots();
      const y = be.now();
      fe.delta = En(0, 1e3 / 60, y - fe.timestamp), fe.timestamp = y, fe.isProcessing = !0, ef.update.process(fe), ef.preRender.process(fe), ef.render.process(fe), fe.isProcessing = !1;
    }
    didUpdate() {
      this.updateScheduled || (this.updateScheduled = !0, fh.read(this.scheduleUpdate));
    }
    clearAllSnapshots() {
      this.nodes.forEach(YE), this.sharedNodes.forEach(JE);
    }
    scheduleUpdateProjection() {
      this.projectionUpdateScheduled || (this.projectionUpdateScheduled = !0, Vt.preRender(this.updateProjection, !1, !0));
    }
    scheduleCheckAfterUnmount() {
      Vt.postRender(() => {
        this.isLayoutDirty ? this.root.didUpdate() : this.root.checkUpdateFailed();
      });
    }
    /**
     * Update measurements
     */
    updateSnapshot() {
      this.snapshot || !this.instance || (this.snapshot = this.measure(), this.snapshot && !Se(this.snapshot.measuredBox.x) && !Se(this.snapshot.measuredBox.y) && (this.snapshot = void 0));
    }
    updateLayout() {
      if (!this.instance || (this.updateScroll(), !(this.options.alwaysMeasureLayout && this.isLead()) && !this.isLayoutDirty))
        return;
      if (this.resumeFrom && !this.resumeFrom.instance)
        for (let v = 0; v < this.path.length; v++)
          this.path[v].updateScroll();
      const h = this.layout;
      this.layout = this.measure(!1), this.layoutVersion++, this.layoutCorrected || (this.layoutCorrected = Ft()), this.isLayoutDirty = !1, this.projectionDelta = void 0, this.notifyListeners("measure", this.layout.layoutBox);
      const { visualElement: y } = this.options;
      y && y.notify("LayoutMeasure", this.layout.layoutBox, h ? h.layoutBox : void 0);
    }
    updateScroll(h = "measure") {
      let y = !!(this.options.layoutScroll && this.instance);
      if (this.scroll && this.scroll.animationId === this.root.animationId && this.scroll.phase === h && (y = !1), y && this.instance) {
        const v = o(this.instance);
        this.scroll = {
          animationId: this.root.animationId,
          phase: h,
          isRoot: v,
          offset: r(this.instance),
          wasRoot: this.scroll ? this.scroll.isRoot : v
        };
      }
    }
    resetTransform() {
      if (!c)
        return;
      const h = this.isLayoutDirty || this.shouldResetTransform || this.options.alwaysMeasureLayout, y = this.projectionDelta && !Hv(this.projectionDelta), v = this.getTransformTemplate(), b = v ? v(this.latestValues, "") : void 0, g = b !== this.prevTransformTemplateValue;
      h && this.instance && (y || Ka(this.latestValues) || g) && (c(this.instance, b), this.shouldResetTransform = !1, this.scheduleRender());
    }
    measure(h = !0) {
      const y = this.measurePageBox();
      let v = this.removeElementScroll(y);
      return h && (v = this.removeTransform(v)), WE(v), {
        animationId: this.root.animationId,
        measuredBox: y,
        layoutBox: v,
        latestValues: {},
        source: this.id
      };
    }
    measurePageBox() {
      const { visualElement: h } = this.options;
      if (!h)
        return Ft();
      const y = h.measureViewportBox();
      if (!(this.scroll?.wasRoot || this.path.some(IE))) {
        const { scroll: b } = this.root;
        b && (Tn(y.x, b.offset.x), Tn(y.y, b.offset.y));
      }
      return y;
    }
    removeElementScroll(h) {
      const y = Ft();
      if (an(y, h), this.scroll?.wasRoot)
        return y;
      for (let v = 0; v < this.path.length; v++) {
        const b = this.path[v], { scroll: g, options: p } = b;
        b !== this.root && g && p.layoutScroll && (g.wasRoot && an(y, h), Tn(y.x, g.offset.x), Tn(y.y, g.offset.y));
      }
      return y;
    }
    applyTransform(h, y = !1, v) {
      const b = v || Ft();
      an(b, h);
      for (let g = 0; g < this.path.length; g++) {
        const p = this.path[g];
        !y && p.options.layoutScroll && p.scroll && p !== p.root && (Tn(b.x, -p.scroll.offset.x), Tn(b.y, -p.scroll.offset.y)), Ka(p.latestValues) && Ju(b, p.latestValues, p.layout?.layoutBox);
      }
      return Ka(this.latestValues) && Ju(b, this.latestValues, this.layout?.layoutBox), b;
    }
    removeTransform(h) {
      const y = Ft();
      an(y, h);
      for (let v = 0; v < this.path.length; v++) {
        const b = this.path[v];
        if (!Ka(b.latestValues))
          continue;
        let g;
        b.instance && (Hf(b.latestValues) && b.updateSnapshot(), g = Ft(), an(g, b.measurePageBox())), L0(y, b.latestValues, b.snapshot?.layoutBox, g);
      }
      return Ka(this.latestValues) && L0(y, this.latestValues), y;
    }
    setTargetDelta(h) {
      this.targetDelta = h, this.root.scheduleUpdateProjection(), this.isProjectionDirty = !0;
    }
    setOptions(h) {
      this.options = {
        ...this.options,
        ...h,
        crossfade: h.crossfade !== void 0 ? h.crossfade : !0
      };
    }
    clearMeasurements() {
      this.scroll = void 0, this.layout = void 0, this.snapshot = void 0, this.prevTransformTemplateValue = void 0, this.targetDelta = void 0, this.target = void 0, this.isLayoutDirty = !1;
    }
    forceRelativeParentToResolveTarget() {
      this.relativeParent && this.relativeParent.resolvedRelativeTargetAt !== fe.timestamp && this.relativeParent.resolveTargetDelta(!0);
    }
    resolveTargetDelta(h = !1) {
      const y = this.getLead();
      this.isProjectionDirty || (this.isProjectionDirty = y.isProjectionDirty), this.isTransformDirty || (this.isTransformDirty = y.isTransformDirty), this.isSharedProjectionDirty || (this.isSharedProjectionDirty = y.isSharedProjectionDirty);
      const v = !!this.resumingFrom || this !== y;
      if (!(h || v && this.isSharedProjectionDirty || this.isProjectionDirty || this.parent?.isProjectionDirty || this.attemptToResolveRelativeTarget || this.root.updateBlockedByResize))
        return;
      const { layout: g, layoutId: p } = this.options;
      if (!this.layout || !(g || p))
        return;
      this.resolvedRelativeTargetAt = fe.timestamp;
      const T = this.getClosestProjectingParent();
      T && this.linkedParentVersion !== T.layoutVersion && !T.options.layoutRoot && this.removeRelativeTarget(), !this.targetDelta && !this.relativeTarget && (this.options.layoutAnchor !== !1 && T && T.layout ? this.createRelativeTarget(T, this.layout.layoutBox, T.layout.layoutBox) : this.removeRelativeTarget()), !(!this.relativeTarget && !this.targetDelta) && (this.target || (this.target = Ft(), this.targetWithTransforms = Ft()), this.relativeTarget && this.relativeTargetOrigin && this.relativeParent && this.relativeParent.target ? (this.forceRelativeParentToResolveTarget(), bE(this.target, this.relativeTarget, this.relativeParent.target, this.options.layoutAnchor || void 0)) : this.targetDelta ? (this.resumingFrom ? this.applyTransform(this.layout.layoutBox, !1, this.target) : an(this.target, this.layout.layoutBox), Dv(this.target, this.targetDelta)) : an(this.target, this.layout.layoutBox), this.attemptToResolveRelativeTarget && (this.attemptToResolveRelativeTarget = !1, this.options.layoutAnchor !== !1 && T && !!T.resumingFrom == !!this.resumingFrom && !T.options.layoutScroll && T.target && this.animationProgress !== 1 ? this.createRelativeTarget(T, this.target, T.target) : this.relativeParent = this.relativeTarget = void 0));
    }
    getClosestProjectingParent() {
      if (!(!this.parent || Hf(this.parent.latestValues) || Mv(this.parent.latestValues)))
        return this.parent.isProjecting() ? this.parent : this.parent.getClosestProjectingParent();
    }
    isProjecting() {
      return !!((this.relativeTarget || this.targetDelta || this.options.layoutRoot) && this.layout);
    }
    createRelativeTarget(h, y, v) {
      this.relativeParent = h, this.linkedParentVersion = h.layoutVersion, this.forceRelativeParentToResolveTarget(), this.relativeTarget = Ft(), this.relativeTargetOrigin = Ft(), lo(this.relativeTargetOrigin, y, v, this.options.layoutAnchor || void 0), an(this.relativeTarget, this.relativeTargetOrigin);
    }
    removeRelativeTarget() {
      this.relativeParent = this.relativeTarget = void 0;
    }
    calcProjection() {
      const h = this.getLead(), y = !!this.resumingFrom || this !== h;
      let v = !0;
      if ((this.isProjectionDirty || this.parent?.isProjectionDirty) && (v = !1), y && (this.isSharedProjectionDirty || this.isTransformDirty) && (v = !1), this.resolvedRelativeTargetAt === fe.timestamp && (v = !1), v)
        return;
      const { layout: b, layoutId: g } = this.options;
      if (this.isTreeAnimating = !!(this.parent && this.parent.isTreeAnimating || this.currentAnimation || this.pendingAnimation), this.isTreeAnimating || (this.targetDelta = this.relativeTarget = void 0), !this.layout || !(b || g))
        return;
      an(this.layoutCorrected, this.layout.layoutBox);
      const p = this.treeScale.x, T = this.treeScale.y;
      k2(this.layoutCorrected, this.treeScale, this.path, y), h.layout && !h.target && (this.treeScale.x !== 1 || this.treeScale.y !== 1) && (h.target = h.layout.layoutBox, h.targetWithTransforms = Ft());
      const { target: V } = h;
      if (!V) {
        this.prevProjectionDelta && (this.createProjectionDeltas(), this.scheduleRender());
        return;
      }
      !this.projectionDelta || !this.prevProjectionDelta ? this.createProjectionDeltas() : (w0(this.prevProjectionDelta.x, this.projectionDelta.x), w0(this.prevProjectionDelta.y, this.projectionDelta.y)), Il(this.projectionDelta, this.layoutCorrected, V, this.latestValues), (this.treeScale.x !== p || this.treeScale.y !== T || !Q0(this.projectionDelta.x, this.prevProjectionDelta.x) || !Q0(this.projectionDelta.y, this.prevProjectionDelta.y)) && (this.hasProjected = !0, this.scheduleRender(), this.notifyListeners("projectionUpdate", V));
    }
    hide() {
      this.isVisible = !1;
    }
    show() {
      this.isVisible = !0;
    }
    scheduleRender(h = !0) {
      if (this.options.visualElement?.scheduleRender(), h) {
        const y = this.getStack();
        y && y.scheduleRender();
      }
      this.resumingFrom && !this.resumingFrom.instance && (this.resumingFrom = void 0);
    }
    createProjectionDeltas() {
      this.prevProjectionDelta = Ki(), this.projectionDelta = Ki(), this.projectionDeltaWithTransform = Ki();
    }
    setAnimationOrigin(h, y = !1, v) {
      const b = this.snapshot, g = b ? b.latestValues : {}, p = { ...this.latestValues }, T = Ki();
      (!this.relativeParent || !this.relativeParent.options.layoutRoot) && (this.relativeTarget = this.relativeTargetOrigin = void 0), this.attemptToResolveRelativeTarget = !y;
      const V = Ft(), z = b ? b.source : void 0, B = this.layout ? this.layout.source : void 0, j = z !== B, L = this.getStack(), Y = !L || L.members.length <= 1, U = !!(j && !Y && this.options.crossfade === !0 && !this.path.some(PE));
      this.animationProgress = 0;
      let G;
      const nt = v?.interpolateProjection(h);
      this.mixTargetDelta = (rt) => {
        const J = rt / 1e3, Q = nt?.(J);
        Q ? (T.x.translate = Q.x, T.x.scale = wt(h.x.scale, 1, J), T.x.origin = h.x.origin, T.x.originPoint = h.x.originPoint, T.y.translate = Q.y, T.y.scale = wt(h.y.scale, 1, J), T.y.origin = h.y.origin, T.y.originPoint = h.y.originPoint) : (W0(T.x, h.x, J), W0(T.y, h.y, J)), this.setTargetDelta(T), this.relativeTarget && this.relativeTargetOrigin && this.layout && this.relativeParent && this.relativeParent.layout && (lo(V, this.layout.layoutBox, this.relativeParent.layout.layoutBox, this.options.layoutAnchor || void 0), kE(this.relativeTarget, this.relativeTargetOrigin, V, J), G && EE(this.relativeTarget, G) && (this.isProjectionDirty = !1), G || (G = Ft()), an(G, this.relativeTarget)), j && (this.animationValues = p, DE(p, g, this.latestValues, J, U, Y)), Q && Q.rotate !== void 0 && (this.animationValues || (this.animationValues = p), this.animationValues.pathRotation = Q.rotate), this.root.scheduleUpdateProjection(), this.scheduleRender(), this.animationProgress = J;
      }, this.mixTargetDelta(this.options.layoutRoot ? 1e3 : 0);
    }
    startAnimation(h) {
      this.notifyListeners("animationStart"), this.currentAnimation?.stop(), this.resumingFrom?.currentAnimation?.stop(), this.pendingAnimation && (va(this.pendingAnimation), this.pendingAnimation = void 0), this.pendingAnimation = Vt.update(() => {
        Pu.hasAnimatedSinceResize = !0, this.motionValue || (this.motionValue = ki(0)), this.motionValue.jump(0, !1), this.currentAnimation = NE(this.motionValue, [0, 1e3], {
          ...h,
          velocity: 0,
          isSync: !0,
          onUpdate: (y) => {
            this.mixTargetDelta(y), h.onUpdate && h.onUpdate(y);
          },
          onComplete: () => {
            h.onComplete && h.onComplete(), this.completeAnimation();
          }
        }), this.resumingFrom && (this.resumingFrom.currentAnimation = this.currentAnimation), this.pendingAnimation = void 0;
      });
    }
    completeAnimation() {
      this.resumingFrom && (this.resumingFrom.currentAnimation = void 0, this.resumingFrom.preserveOpacity = void 0);
      const h = this.getStack();
      h && h.exitAnimationComplete(), this.resumingFrom = this.currentAnimation = this.animationValues = void 0, this.notifyListeners("animationComplete");
    }
    finishAnimation() {
      this.currentAnimation && (this.mixTargetDelta && this.mixTargetDelta(VE), this.currentAnimation.stop()), this.completeAnimation();
    }
    applyTransformsToTarget() {
      const h = this.getLead();
      let { targetWithTransforms: y, target: v, layout: b, latestValues: g } = h;
      if (!(!y || !v || !b)) {
        if (this !== h && this.layout && b && Xv(this.options.animationType, this.layout.layoutBox, b.layoutBox)) {
          v = this.target || Ft();
          const p = Se(this.layout.layoutBox.x);
          v.x.min = h.target.x.min, v.x.max = v.x.min + p;
          const T = Se(this.layout.layoutBox.y);
          v.y.min = h.target.y.min, v.y.max = v.y.min + T;
        }
        an(y, v), Ju(y, g), Il(this.projectionDeltaWithTransform, this.layoutCorrected, y, g);
      }
    }
    registerSharedNode(h, y) {
      this.sharedNodes.has(h) || this.sharedNodes.set(h, new wE()), this.sharedNodes.get(h).add(y);
      const b = y.options.initialPromotionConfig;
      y.promote({
        transition: b ? b.transition : void 0,
        preserveFollowOpacity: b && b.shouldPreserveFollowOpacity ? b.shouldPreserveFollowOpacity(y) : void 0
      });
    }
    isLead() {
      const h = this.getStack();
      return h ? h.lead === this : !0;
    }
    getLead() {
      const { layoutId: h } = this.options;
      return h ? this.getStack()?.lead || this : this;
    }
    getPrevLead() {
      const { layoutId: h } = this.options;
      return h ? this.getStack()?.prevLead : void 0;
    }
    getStack() {
      const { layoutId: h } = this.options;
      if (h)
        return this.root.sharedNodes.get(h);
    }
    promote({ needsReset: h, transition: y, preserveFollowOpacity: v } = {}) {
      const b = this.getStack();
      b && b.promote(this, v), h && (this.projectionDelta = void 0, this.needsReset = !0), y && this.setOptions({ transition: y });
    }
    relegate() {
      const h = this.getStack();
      return h ? h.relegate(this) : !1;
    }
    resetSkewAndRotation() {
      const { visualElement: h } = this.options;
      if (!h)
        return;
      let y = !1;
      const { latestValues: v } = h;
      if ((v.z || v.rotate || v.rotateX || v.rotateY || v.rotateZ || v.skewX || v.skewY) && (y = !0), !y)
        return;
      const b = {};
      v.z && ff("z", h, b, this.animationValues);
      for (let g = 0; g < cf.length; g++)
        ff(`rotate${cf[g]}`, h, b, this.animationValues), ff(`skew${cf[g]}`, h, b, this.animationValues);
      h.render();
      for (const g in b)
        h.setStaticValue(g, b[g]), this.animationValues && (this.animationValues[g] = b[g]);
      h.scheduleRender();
    }
    applyProjectionStyles(h, y) {
      if (!this.instance || this.isSVG)
        return;
      if (!this.isVisible) {
        h.visibility = "hidden";
        return;
      }
      const v = this.getTransformTemplate();
      if (this.needsReset) {
        this.needsReset = !1, h.visibility = "", h.opacity = "", h.pointerEvents = ku(y?.pointerEvents) || "", h.transform = v ? v(this.latestValues, "") : "none";
        return;
      }
      const b = this.getLead();
      if (!this.projectionDelta || !this.layout || !b.target) {
        this.options.layoutId && (h.opacity = this.latestValues.opacity !== void 0 ? this.latestValues.opacity : 1, h.pointerEvents = ku(y?.pointerEvents) || ""), this.hasProjected && !Ka(this.latestValues) && (h.transform = v ? v({}, "") : "none", this.hasProjected = !1);
        return;
      }
      h.visibility = "";
      const g = b.animationValues || b.latestValues;
      this.applyTransformsToTarget();
      let p = AE(this.projectionDeltaWithTransform, this.treeScale, g);
      v && (p = v(g, p)), h.transform = p;
      const { x: T, y: V } = this.projectionDelta;
      h.transformOrigin = `${T.origin * 100}% ${V.origin * 100}% 0`, b.animationValues ? h.opacity = b === this ? g.opacity ?? this.latestValues.opacity ?? 1 : this.preserveOpacity ? this.latestValues.opacity : g.opacityExit : h.opacity = b === this ? g.opacity !== void 0 ? g.opacity : "" : g.opacityExit !== void 0 ? g.opacityExit : 0;
      for (const z in Yf) {
        if (g[z] === void 0)
          continue;
        const { correct: B, applyTo: j, isCSSVariable: L } = Yf[z], Y = p === "none" ? g[z] : B(g[z], b);
        if (j) {
          const U = j.length;
          for (let G = 0; G < U; G++)
            h[j[G]] = Y;
        } else
          L ? this.options.visualElement.renderState.vars[z] = Y : h[z] = Y;
      }
      this.options.layoutId && (h.pointerEvents = b === this ? ku(y?.pointerEvents) || "" : "none");
    }
    clearSnapshot() {
      this.resumeFrom = this.snapshot = void 0;
    }
    // Only run on root
    resetTree() {
      this.root.nodes.forEach((h) => h.currentAnimation?.stop()), this.root.nodes.forEach(k0), this.root.sharedNodes.clear();
    }
  };
}
function UE(i) {
  i.updateLayout();
}
function BE(i) {
  const l = i.resumeFrom?.snapshot || i.snapshot;
  if (i.isLead() && i.layout && l && i.hasListeners("didUpdate")) {
    const { layoutBox: r, measuredBox: o } = i.layout, { animationType: c } = i.options, d = l.source !== i.layout.source;
    if (c === "size")
      Sn((g) => {
        const p = d ? l.measuredBox[g] : l.layoutBox[g], T = Se(p);
        p.min = r[g].min, p.max = p.min + T;
      });
    else if (c === "x" || c === "y") {
      const g = c === "x" ? "y" : "x";
      qf(d ? l.measuredBox[g] : l.layoutBox[g], r[g]);
    } else Xv(c, l.layoutBox, r) && Sn((g) => {
      const p = d ? l.measuredBox[g] : l.layoutBox[g], T = Se(r[g]);
      p.max = p.min + T, i.relativeTarget && !i.currentAnimation && (i.isProjectionDirty = !0, i.relativeTarget[g].max = i.relativeTarget[g].min + T);
    });
    const h = Ki();
    Il(h, r, l.layoutBox);
    const y = Ki();
    d ? Il(y, i.applyTransform(o, !0), l.measuredBox) : Il(y, r, l.layoutBox);
    const v = !Hv(h);
    let b = !1;
    if (!i.resumeFrom) {
      const g = i.getClosestProjectingParent();
      if (g && !g.resumeFrom) {
        const { snapshot: p, layout: T } = g;
        if (p && T) {
          const V = i.options.layoutAnchor || void 0, z = Ft();
          lo(z, l.layoutBox, p.layoutBox, V);
          const B = Ft();
          lo(B, r, T.layoutBox, V), Lv(z, B) || (b = !0), g.options.layoutRoot && (i.relativeTarget = B, i.relativeTargetOrigin = z, i.relativeParent = g);
        }
      }
    }
    i.notifyListeners("didUpdate", {
      layout: r,
      snapshot: l,
      delta: y,
      layoutDelta: h,
      hasLayoutChanged: v,
      hasRelativeLayoutChanged: b
    });
  } else if (i.isLead()) {
    const { onExitComplete: r } = i.options;
    r && r();
  }
  i.options.transition = void 0;
}
function HE(i) {
  i.parent && (i.isProjecting() || (i.isProjectionDirty = i.parent.isProjectionDirty), i.isSharedProjectionDirty || (i.isSharedProjectionDirty = !!(i.isProjectionDirty || i.parent.isProjectionDirty || i.parent.isSharedProjectionDirty)), i.isTransformDirty || (i.isTransformDirty = i.parent.isTransformDirty));
}
function LE(i) {
  i.isProjectionDirty = i.isSharedProjectionDirty = i.isTransformDirty = !1;
}
function YE(i) {
  i.clearSnapshot();
}
function k0(i) {
  i.clearMeasurements();
}
function qE(i) {
  i.isLayoutDirty = !0, i.updateLayout();
}
function P0(i) {
  i.isLayoutDirty = !1;
}
function GE(i) {
  i.isAnimationBlocked && i.layout && !i.isLayoutDirty && (i.snapshot = i.layout, i.isLayoutDirty = !0);
}
function XE(i) {
  const { visualElement: l } = i.options;
  l && l.getProps().onBeforeLayoutMeasure && l.notify("BeforeLayoutMeasure"), i.resetTransform();
}
function F0(i) {
  i.finishAnimation(), i.targetDelta = i.relativeTarget = i.target = void 0, i.isProjectionDirty = !0;
}
function QE(i) {
  i.resolveTargetDelta();
}
function ZE(i) {
  i.calcProjection();
}
function KE(i) {
  i.resetSkewAndRotation();
}
function JE(i) {
  i.removeLeadSnapshot();
}
function W0(i, l, r) {
  i.translate = wt(l.translate, 0, r), i.scale = wt(l.scale, 1, r), i.origin = l.origin, i.originPoint = l.originPoint;
}
function I0(i, l, r, o) {
  i.min = wt(l.min, r.min, o), i.max = wt(l.max, r.max, o);
}
function kE(i, l, r, o) {
  I0(i.x, l.x, r.x, o), I0(i.y, l.y, r.y, o);
}
function PE(i) {
  return i.animationValues && i.animationValues.opacityExit !== void 0;
}
const FE = {
  duration: 0.45,
  ease: [0.4, 0, 0.1, 1]
}, $0 = (i) => typeof navigator < "u" && navigator.userAgent && navigator.userAgent.toLowerCase().includes(i), tg = $0("applewebkit/") && !$0("chrome/") ? Math.round : Pe;
function eg(i) {
  i.min = tg(i.min), i.max = tg(i.max);
}
function WE(i) {
  eg(i.x), eg(i.y);
}
function Xv(i, l, r) {
  return i === "position" || i === "preserve-aspect" && !vE(X0(l), X0(r), 0.2);
}
function IE(i) {
  return i !== i.root && i.scroll?.wasRoot;
}
const $E = Gv({
  attachResizeListener: (i, l) => as(i, "resize", l),
  measureScroll: () => ({
    x: document.documentElement.scrollLeft || document.body?.scrollLeft || 0,
    y: document.documentElement.scrollTop || document.body?.scrollTop || 0
  }),
  checkIsScrollRoot: () => !0
}), hf = {
  current: void 0
}, Qv = Gv({
  measureScroll: (i) => ({
    x: i.scrollLeft,
    y: i.scrollTop
  }),
  defaultParent: () => {
    if (!hf.current) {
      const i = new $E({});
      i.mount(window), i.setOptions({ layoutScroll: !0 }), hf.current = i;
    }
    return hf.current;
  },
  resetTransform: (i, l) => {
    i.style.transform = l !== void 0 ? l : "none";
  },
  checkIsScrollRoot: (i) => window.getComputedStyle(i).position === "fixed"
}), Zv = K.createContext({
  transformPagePoint: (i) => i,
  isStatic: !1,
  reducedMotion: "never"
});
function tA(i = !0) {
  const l = K.useContext(kf);
  if (l === null)
    return [!0, null];
  const { isPresent: r, onExitComplete: o, register: c } = l, d = K.useId();
  K.useEffect(() => {
    if (i)
      return c(d);
  }, [i]);
  const h = K.useCallback(() => i && o && o(d), [d, o, i]);
  return !r && o ? [!1, h] : [!0];
}
const Kv = K.createContext({ strict: !1 }), ng = {
  animation: [
    "animate",
    "variants",
    "whileHover",
    "whileTap",
    "exit",
    "whileInView",
    "whileFocus",
    "whileDrag"
  ],
  exit: ["exit"],
  drag: ["drag", "dragControls"],
  focus: ["whileFocus"],
  hover: ["whileHover", "onHoverStart", "onHoverEnd"],
  tap: ["whileTap", "onTap", "onTapStart", "onTapCancel"],
  pan: ["onPan", "onPanStart", "onPanSessionStart", "onPanEnd"],
  inView: ["whileInView", "onViewportEnter", "onViewportLeave"],
  layout: ["layout", "layoutId"]
};
let ag = !1;
function eA() {
  if (ag)
    return;
  const i = {};
  for (const l in ng)
    i[l] = {
      isEnabled: (r) => ng[l].some((o) => !!r[o])
    };
  xv(i), ag = !0;
}
function Jv() {
  return eA(), Q2();
}
function nA(i) {
  const l = Jv();
  for (const r in i)
    l[r] = {
      ...l[r],
      ...i[r]
    };
  xv(l);
}
const aA = /* @__PURE__ */ new Set([
  "animate",
  "exit",
  "variants",
  "initial",
  "style",
  "values",
  "variants",
  "transition",
  "transformTemplate",
  "custom",
  "inherit",
  "onBeforeLayoutMeasure",
  "onAnimationStart",
  "onAnimationComplete",
  "onUpdate",
  "onDragStart",
  "onDrag",
  "onDragEnd",
  "onMeasureDragConstraints",
  "onDirectionLock",
  "onDragTransitionEnd",
  "_dragX",
  "_dragY",
  "onHoverStart",
  "onHoverEnd",
  "onViewportEnter",
  "onViewportLeave",
  "globalTapTarget",
  "propagate",
  "ignoreStrict",
  "viewport"
]);
function so(i) {
  return i.startsWith("while") || i.startsWith("drag") && i !== "draggable" || i.startsWith("layout") || i.startsWith("onTap") || i.startsWith("onPan") || i.startsWith("onLayout") || aA.has(i);
}
let kv = (i) => !so(i);
function iA(i) {
  typeof i == "function" && (kv = (l) => l.startsWith("on") ? !so(l) : i(l));
}
try {
  iA(require("@emotion/is-prop-valid").default);
} catch {
}
function lA(i, l, r) {
  const o = {};
  for (const c in i)
    c === "values" && typeof i.values == "object" || he(i[c]) || (kv(c) || r === !0 && so(c) || !l && !so(c) || // If trying to use native HTML drag events, forward drag listeners
    i.draggable && c.startsWith("onDrag")) && (o[c] = i[c]);
  return o;
}
const ho = /* @__PURE__ */ K.createContext({});
function sA(i, l) {
  if (fo(i)) {
    const { initial: r, animate: o } = i;
    return {
      initial: r === !1 || ns(r) ? r : void 0,
      animate: ns(o) ? o : void 0
    };
  }
  return i.inherit !== !1 ? l : {};
}
function uA(i) {
  const { initial: l, animate: r } = sA(i, K.useContext(ho));
  return K.useMemo(() => ({ initial: l, animate: r }), [ig(l), ig(r)]);
}
function ig(i) {
  return Array.isArray(i) ? i.join(" ") : i;
}
const bh = () => ({
  style: {},
  transform: {},
  transformOrigin: {},
  vars: {}
});
function Pv(i, l, r) {
  for (const o in l)
    !he(l[o]) && !Nv(o, r) && (i[o] = l[o]);
}
function oA({ transformTemplate: i }, l) {
  return K.useMemo(() => {
    const r = bh();
    return gh(r, l, i), Object.assign({}, r.vars, r.style);
  }, [l]);
}
function rA(i, l) {
  const r = i.style || {}, o = {};
  return Pv(o, r, i), Object.assign(o, oA(i, l)), o;
}
function cA(i, l) {
  const r = {}, o = rA(i, l);
  return i.drag && i.dragListener !== !1 && (r.draggable = !1, o.userSelect = o.WebkitUserSelect = o.WebkitTouchCallout = "none", o.touchAction = i.drag === !0 ? "none" : `pan-${i.drag === "x" ? "y" : "x"}`), i.tabIndex === void 0 && (i.onTap || i.onTapStart || i.whileTap) && (r.tabIndex = 0), r.style = o, r;
}
const Fv = () => ({
  ...bh(),
  attrs: {}
});
function fA(i, l, r, o) {
  const c = K.useMemo(() => {
    const d = Fv();
    return zv(d, l, _v(o), i.transformTemplate, i.style), {
      ...d.attrs,
      style: { ...d.style }
    };
  }, [l]);
  if (i.style) {
    const d = {};
    Pv(d, i.style, i), c.style = { ...d, ...c.style };
  }
  return c;
}
const hA = [
  "animate",
  "circle",
  "defs",
  "desc",
  "ellipse",
  "g",
  "image",
  "line",
  "filter",
  "marker",
  "mask",
  "metadata",
  "path",
  "pattern",
  "polygon",
  "polyline",
  "rect",
  "stop",
  "switch",
  "symbol",
  "svg",
  "text",
  "tspan",
  "use",
  "view"
];
function Sh(i) {
  return (
    /**
     * If it's not a string, it's a custom React component. Currently we only support
     * HTML custom React components.
     */
    typeof i != "string" || /**
     * If it contains a dash, the element is a custom HTML webcomponent.
     */
    i.includes("-") ? !1 : (
      /**
       * If it's in our list of lowercase SVG tags, it's an SVG component
       */
      !!(hA.indexOf(i) > -1 || /**
       * If it contains a capital letter, it's an SVG component
       */
      /[A-Z]/u.test(i))
    )
  );
}
function dA(i, l, r, { latestValues: o }, c, d = !1, h) {
  const v = (h ?? Sh(i) ? fA : cA)(l, o, c, i), b = lA(l, typeof i == "string", d), g = i !== K.Fragment ? { ...b, ...v, ref: r } : {}, { children: p } = l, T = K.useMemo(() => he(p) ? p.get() : p, [p]);
  return K.createElement(i, {
    ...g,
    children: T
  });
}
function mA({ scrapeMotionValuesFromProps: i, createRenderState: l }, r, o, c) {
  return {
    latestValues: yA(r, o, c, i),
    renderState: l()
  };
}
function yA(i, l, r, o) {
  const c = {}, d = o(i, {});
  for (const T in d)
    c[T] = ku(d[T]);
  let { initial: h, animate: y } = i;
  const v = fo(i), b = Sv(i);
  l && b && !v && i.inherit !== !1 && (h === void 0 && (h = l.initial), y === void 0 && (y = l.animate));
  let g = r ? r.initial === !1 : !1;
  g = g || h === !1;
  const p = g ? y : h;
  if (p && typeof p != "boolean" && !co(p)) {
    const T = Array.isArray(p) ? p : [p];
    for (let V = 0; V < T.length; V++) {
      const z = oh(i, T[V]);
      if (z) {
        const { transitionEnd: B, transition: j, ...L } = z;
        for (const Y in L) {
          let U = L[Y];
          if (Array.isArray(U)) {
            const G = g ? U.length - 1 : 0;
            U = U[G];
          }
          U !== null && (c[Y] = U);
        }
        for (const Y in B)
          c[Y] = B[Y];
      }
    }
  }
  return c;
}
const Wv = (i) => (l, r) => {
  const o = K.useContext(ho), c = K.useContext(kf), d = () => mA(i, l, o, c);
  return r ? d() : mT(d);
}, pA = /* @__PURE__ */ Wv({
  scrapeMotionValuesFromProps: vh,
  createRenderState: bh
}), gA = /* @__PURE__ */ Wv({
  scrapeMotionValuesFromProps: wv,
  createRenderState: Fv
}), vA = /* @__PURE__ */ Symbol.for("motionComponentSymbol");
function bA(i, l, r) {
  const o = K.useRef(r);
  K.useInsertionEffect(() => {
    o.current = r;
  });
  const c = K.useRef(null);
  return K.useCallback((d) => {
    d && i.onMount?.(d), l && (d ? l.mount(d) : l.unmount());
    const h = o.current;
    if (typeof h == "function")
      if (d) {
        const y = h(d);
        typeof y == "function" && (c.current = y);
      } else c.current ? (c.current(), c.current = null) : h(d);
    else h && (h.current = d);
  }, [l]);
}
const Iv = K.createContext({});
function Xi(i) {
  return i && typeof i == "object" && Object.prototype.hasOwnProperty.call(i, "current");
}
function SA(i, l, r, o, c, d) {
  const { visualElement: h } = K.useContext(ho), y = K.useContext(Kv), v = K.useContext(kf), b = K.useContext(Zv), g = b.reducedMotion, p = b.skipAnimations, T = K.useRef(null), V = K.useRef(!1);
  o = o || y.renderer, !T.current && o && (T.current = o(i, {
    visualState: l,
    parent: h,
    props: r,
    presenceContext: v,
    blockInitialAnimation: v ? v.initial === !1 : !1,
    reducedMotionConfig: g,
    skipAnimations: p,
    isSVG: d
  }), V.current && T.current && (T.current.manuallyAnimateOnMount = !0));
  const z = T.current, B = K.useContext(Iv);
  z && !z.projection && c && (z.type === "html" || z.type === "svg") && TA(T.current, r, c, B);
  const j = K.useRef(!1);
  K.useInsertionEffect(() => {
    z && j.current && z.update(r, v);
  });
  const L = r[ov], Y = K.useRef(!!L && typeof window < "u" && !window.MotionHandoffIsComplete?.(L) && window.MotionHasOptimisedAnimation?.(L));
  return pT(() => {
    V.current = !0, z && (j.current = !0, window.MotionIsMounted = !0, z.updateFeatures(), z.scheduleRenderMicrotask(), Y.current && z.animationState && z.animationState.animateChanges());
  }), K.useEffect(() => {
    z && (!Y.current && z.animationState && z.animationState.animateChanges(), Y.current && (queueMicrotask(() => {
      window.MotionHandoffMarkAsComplete?.(L);
    }), Y.current = !1), z.enteringChildren = void 0);
  }), z;
}
function TA(i, l, r, o) {
  const { layoutId: c, layout: d, drag: h, dragConstraints: y, layoutScroll: v, layoutRoot: b, layoutAnchor: g, layoutCrossfade: p } = l;
  i.projection = new r(i.latestValues, l["data-framer-portal-id"] ? void 0 : $v(i.parent)), i.projection.setOptions({
    layoutId: c,
    layout: d,
    alwaysMeasureLayout: !!h || y && Xi(y),
    visualElement: i,
    /**
     * TODO: Update options in an effect. This could be tricky as it'll be too late
     * to update by the time layout animations run.
     * We also need to fix this safeToRemove by linking it up to the one returned by usePresence,
     * ensuring it gets called if there's no potential layout animations.
     *
     */
    animationType: typeof d == "string" ? d : "both",
    initialPromotionConfig: o,
    crossfade: p,
    layoutScroll: v,
    layoutRoot: b,
    layoutAnchor: g
  });
}
function $v(i) {
  if (i)
    return i.options.allowProjection !== !1 ? i.projection : $v(i.parent);
}
function df(i, { forwardMotionProps: l = !1, type: r } = {}, o, c) {
  o && nA(o);
  const d = r ? r === "svg" : Sh(i), h = d ? gA : pA;
  function y(b, g) {
    let p;
    const T = {
      ...K.useContext(Zv),
      ...b,
      layoutId: xA(b)
    }, { isStatic: V } = T, z = uA(b), B = h(b, V);
    if (!V && typeof window < "u") {
      EA();
      const j = AA(T);
      p = j.MeasureLayout, z.visualElement = SA(i, B, T, c, j.ProjectionNode, d);
    }
    return R.jsxs(ho.Provider, { value: z, children: [p && z.visualElement ? R.jsx(p, { visualElement: z.visualElement, ...T }) : null, dA(i, b, bA(B, z.visualElement, g), B, V, l, d)] });
  }
  y.displayName = `motion.${typeof i == "string" ? i : `create(${i.displayName ?? i.name ?? ""})`}`;
  const v = K.forwardRef(y);
  return v[vA] = i, v;
}
function xA({ layoutId: i }) {
  const l = K.useContext(Sg).id;
  return l && i !== void 0 ? l + "-" + i : i;
}
function EA(i, l) {
  K.useContext(Kv).strict;
}
function AA(i) {
  const l = Jv(), { drag: r, layout: o } = l;
  if (!r && !o)
    return {};
  const c = { ...r, ...o };
  return {
    MeasureLayout: r?.isEnabled(i) || o?.isEnabled(i) ? c.MeasureLayout : void 0,
    ProjectionNode: c.ProjectionNode
  };
}
function MA(i, l) {
  if (typeof Proxy > "u")
    return df;
  const r = /* @__PURE__ */ new Map(), o = (d, h) => df(d, h, i, l), c = (d, h) => o(d, h);
  return new Proxy(c, {
    /**
     * Called when `motion` is referenced with a prop: `motion.div`, `motion.input` etc.
     * The prop name is passed through as `key` and we can use that to generate a `motion`
     * DOM component with that name.
     */
    get: (d, h) => h === "create" ? o : (r.has(h) || r.set(h, df(h, void 0, i, l)), r.get(h))
  });
}
const DA = (i, l) => l.isSVG ?? Sh(i) ? new uE(l) : new eE(l, {
  allowProjection: i !== K.Fragment
});
class CA extends ba {
  /**
   * We dynamically generate the AnimationState manager as it contains a reference
   * to the underlying animation library. We only want to load that if we load this,
   * so people can optionally code split it out using the `m` component.
   */
  constructor(l) {
    super(l), l.animationState || (l.animationState = hE(l));
  }
  updateAnimationControlsSubscription() {
    const { animate: l } = this.node.getProps();
    co(l) && (this.unmountControls = l.subscribe(this.node));
  }
  /**
   * Subscribe any provided AnimationControls to the component's VisualElement
   */
  mount() {
    this.updateAnimationControlsSubscription();
  }
  update() {
    const { animate: l } = this.node.getProps(), { animate: r } = this.node.prevProps || {};
    l !== r && this.updateAnimationControlsSubscription();
  }
  unmount() {
    this.node.animationState.reset(), this.unmountControls?.();
  }
}
let OA = 0;
class NA extends ba {
  constructor() {
    super(...arguments), this.id = OA++, this.isExitComplete = !1;
  }
  update() {
    if (!this.node.presenceContext)
      return;
    const { isPresent: l, onExitComplete: r } = this.node.presenceContext, { isPresent: o } = this.node.prevPresenceContext || {};
    if (!this.node.animationState || l === o)
      return;
    if (l && o === !1) {
      if (this.isExitComplete) {
        const { initial: d, custom: h } = this.node.getProps();
        if (typeof d == "string" || typeof d == "object" && d !== null && !Array.isArray(d)) {
          const y = Wa(this.node, d, h);
          if (y) {
            const { transition: v, transitionEnd: b, ...g } = y;
            for (const p in g)
              this.node.getValue(p)?.jump(g[p]);
          }
        }
        this.node.animationState.reset(), this.node.animationState.animateChanges();
      } else
        this.node.animationState.setActive("exit", !1);
      this.isExitComplete = !1;
      return;
    }
    const c = this.node.animationState.setActive("exit", !l);
    r && !l && c.then(() => {
      this.isExitComplete = !0, r(this.id);
    });
  }
  mount() {
    const { register: l, onExitComplete: r } = this.node.presenceContext || {};
    r && r(this.id), l && (this.unmount = l(this.id));
  }
  unmount() {
  }
}
const zA = {
  animation: {
    Feature: CA
  },
  exit: {
    Feature: NA
  }
};
function us(i) {
  return {
    point: {
      x: i.pageX,
      y: i.pageY
    }
  };
}
const RA = (i) => (l) => hh(l) && i(l, us(l));
function $l(i, l, r, o) {
  return as(i, l, RA(r), o);
}
const t1 = ({ current: i }) => i ? i.ownerDocument.defaultView : null, lg = (i, l) => Math.abs(i - l);
function _A(i, l) {
  const r = lg(i.x, l.x), o = lg(i.y, l.y);
  return Math.sqrt(r ** 2 + o ** 2);
}
const sg = /* @__PURE__ */ new Set(["auto", "scroll"]);
class e1 {
  constructor(l, r, { transformPagePoint: o, contextWindow: c = window, dragSnapToOrigin: d = !1, distanceThreshold: h = 3, element: y } = {}) {
    if (this.startEvent = null, this.lastMoveEvent = null, this.lastMoveEventInfo = null, this.lastRawMoveEventInfo = null, this.handlers = {}, this.contextWindow = window, this.scrollPositions = /* @__PURE__ */ new Map(), this.removeScrollListeners = null, this.onElementScroll = (z) => {
      this.handleScroll(z.target);
    }, this.onWindowScroll = () => {
      this.handleScroll(window);
    }, this.updatePoint = () => {
      if (!(this.lastMoveEvent && this.lastMoveEventInfo))
        return;
      this.lastRawMoveEventInfo && (this.lastMoveEventInfo = Yu(this.lastRawMoveEventInfo, this.transformPagePoint));
      const z = mf(this.lastMoveEventInfo, this.history), B = this.startEvent !== null, j = _A(z.offset, { x: 0, y: 0 }) >= this.distanceThreshold;
      if (!B && !j)
        return;
      const { point: L } = z, { timestamp: Y } = fe;
      this.history.push({ ...L, timestamp: Y });
      const { onStart: U, onMove: G } = this.handlers;
      B || (U && U(this.lastMoveEvent, z), this.startEvent = this.lastMoveEvent), G && G(this.lastMoveEvent, z);
    }, this.handlePointerMove = (z, B) => {
      this.lastMoveEvent = z, this.lastRawMoveEventInfo = B, this.lastMoveEventInfo = Yu(B, this.transformPagePoint), Vt.update(this.updatePoint, !0);
    }, this.handlePointerUp = (z, B) => {
      this.end();
      const { onEnd: j, onSessionEnd: L, resumeAnimation: Y } = this.handlers;
      if ((this.dragSnapToOrigin || !this.startEvent) && Y && Y(), !(this.lastMoveEvent && this.lastMoveEventInfo))
        return;
      const U = mf(z.type === "pointercancel" ? this.lastMoveEventInfo : Yu(B, this.transformPagePoint), this.history);
      this.startEvent && j && j(z, U), L && L(z, U);
    }, !hh(l))
      return;
    this.dragSnapToOrigin = d, this.handlers = r, this.transformPagePoint = o, this.distanceThreshold = h, this.contextWindow = c || window;
    const v = us(l), b = Yu(v, this.transformPagePoint), { point: g } = b, { timestamp: p } = fe;
    this.history = [{ ...g, timestamp: p }];
    const { onSessionStart: T } = r;
    T && T(l, mf(b, this.history));
    const V = { passive: !0, capture: !0 };
    this.removeListeners = is($l(this.contextWindow, "pointermove", this.handlePointerMove, V), $l(this.contextWindow, "pointerup", this.handlePointerUp, V), $l(this.contextWindow, "pointercancel", this.handlePointerUp, V)), y && this.startScrollTracking(y);
  }
  /**
   * Start tracking scroll on ancestors and window.
   */
  startScrollTracking(l) {
    let r = l.parentElement;
    for (; r; ) {
      const o = getComputedStyle(r);
      (sg.has(o.overflowX) || sg.has(o.overflowY)) && this.scrollPositions.set(r, {
        x: r.scrollLeft,
        y: r.scrollTop
      }), r = r.parentElement;
    }
    this.scrollPositions.set(window, {
      x: window.scrollX,
      y: window.scrollY
    }), window.addEventListener("scroll", this.onElementScroll, {
      capture: !0
    }), window.addEventListener("scroll", this.onWindowScroll), this.removeScrollListeners = () => {
      window.removeEventListener("scroll", this.onElementScroll, {
        capture: !0
      }), window.removeEventListener("scroll", this.onWindowScroll);
    };
  }
  /**
   * Handle scroll compensation during drag.
   *
   * For element scroll: adjusts history origin since pageX/pageY doesn't change.
   * For window scroll: adjusts lastMoveEventInfo since pageX/pageY would change.
   */
  handleScroll(l) {
    const r = this.scrollPositions.get(l);
    if (!r)
      return;
    const o = l === window, c = o ? { x: window.scrollX, y: window.scrollY } : {
      x: l.scrollLeft,
      y: l.scrollTop
    }, d = { x: c.x - r.x, y: c.y - r.y };
    d.x === 0 && d.y === 0 || (o ? this.lastMoveEventInfo && (this.lastMoveEventInfo.point.x += d.x, this.lastMoveEventInfo.point.y += d.y) : this.history.length > 0 && (this.history[0].x -= d.x, this.history[0].y -= d.y), this.scrollPositions.set(l, c), Vt.update(this.updatePoint, !0));
  }
  updateHandlers(l) {
    this.handlers = l;
  }
  end() {
    this.removeListeners && this.removeListeners(), this.removeScrollListeners && this.removeScrollListeners(), this.scrollPositions.clear(), va(this.updatePoint);
  }
}
function Yu(i, l) {
  return l ? { point: l(i.point) } : i;
}
function ug(i, l) {
  return { x: i.x - l.x, y: i.y - l.y };
}
function mf({ point: i }, l) {
  return {
    point: i,
    delta: ug(i, n1(l)),
    offset: ug(i, wA(l)),
    velocity: VA(l, 0.1)
  };
}
function wA(i) {
  return i[0];
}
function n1(i) {
  return i[i.length - 1];
}
function VA(i, l) {
  if (i.length < 2)
    return { x: 0, y: 0 };
  let r = i.length - 1, o = null;
  const c = n1(i);
  for (; r >= 0 && (o = i[r], !(c.timestamp - o.timestamp > /* @__PURE__ */ He(l))); )
    r--;
  if (!o)
    return { x: 0, y: 0 };
  o === i[0] && i.length > 2 && c.timestamp - o.timestamp > /* @__PURE__ */ He(l) * 2 && (o = i[1]);
  const d = /* @__PURE__ */ ke(c.timestamp - o.timestamp);
  if (d === 0)
    return { x: 0, y: 0 };
  const h = {
    x: (c.x - o.x) / d,
    y: (c.y - o.y) / d
  };
  return h.x === 1 / 0 && (h.x = 0), h.y === 1 / 0 && (h.y = 0), h;
}
function jA(i, { min: l, max: r }, o) {
  return l !== void 0 && i < l ? i = o ? wt(l, i, o.min) : Math.max(i, l) : r !== void 0 && i > r && (i = o ? wt(r, i, o.max) : Math.min(i, r)), i;
}
function og(i, l, r) {
  return {
    min: l !== void 0 ? i.min + l : void 0,
    max: r !== void 0 ? i.max + r - (i.max - i.min) : void 0
  };
}
function UA(i, { top: l, left: r, bottom: o, right: c }) {
  return {
    x: og(i.x, r, c),
    y: og(i.y, l, o)
  };
}
function rg(i, l) {
  let r = l.min - i.min, o = l.max - i.max;
  return l.max - l.min < i.max - i.min && ([r, o] = [o, r]), { min: r, max: o };
}
function BA(i, l) {
  return {
    x: rg(i.x, l.x),
    y: rg(i.y, l.y)
  };
}
function HA(i, l) {
  let r = 0.5;
  const o = Se(i), c = Se(l);
  return c > o ? r = /* @__PURE__ */ ts(l.min, l.max - o, i.min) : o > c && (r = /* @__PURE__ */ ts(i.min, i.max - c, l.min)), En(0, 1, r);
}
function LA(i, l) {
  const r = {};
  return l.min !== void 0 && (r.min = l.min - i.min), l.max !== void 0 && (r.max = l.max - i.min), r;
}
const Gf = 0.35;
function YA(i = Gf) {
  return i === !1 ? i = 0 : i === !0 && (i = Gf), {
    x: cg(i, "left", "right"),
    y: cg(i, "top", "bottom")
  };
}
function cg(i, l, r) {
  return {
    min: fg(i, l),
    max: fg(i, r)
  };
}
function fg(i, l) {
  return typeof i == "number" ? i : i[l] || 0;
}
const qA = /* @__PURE__ */ new WeakMap();
class GA {
  constructor(l) {
    this.openDragLock = null, this.isDragging = !1, this.currentDirection = null, this.originPoint = { x: 0, y: 0 }, this.constraints = !1, this.hasMutatedConstraints = !1, this.elastic = Ft(), this.latestPointerEvent = null, this.latestPanInfo = null, this.visualElement = l;
  }
  start(l, { snapToCursor: r = !1, distanceThreshold: o } = {}) {
    const { presenceContext: c } = this.visualElement;
    if (c && c.isPresent === !1)
      return;
    const d = (p) => {
      r && this.snapToCursor(us(p).point), this.stopAnimation();
    }, h = (p, T) => {
      const { drag: V, dragPropagation: z, onDragStart: B } = this.getProps();
      if (V && !z && (this.openDragLock && this.openDragLock(), this.openDragLock = T2(V), !this.openDragLock))
        return;
      this.latestPointerEvent = p, this.latestPanInfo = T, this.isDragging = !0, this.currentDirection = null, this.resolveConstraints(), this.visualElement.projection && (this.visualElement.projection.isAnimationBlocked = !0, this.visualElement.projection.target = void 0), Sn((L) => {
        let Y = this.getAxisMotionValue(L).get() || 0;
        if (xn.test(Y)) {
          const { projection: U } = this.visualElement;
          if (U && U.layout) {
            const G = U.layout.layoutBox[L];
            G && (Y = Se(G) * (parseFloat(Y) / 100));
          }
        }
        this.originPoint[L] = Y;
      }), B && Vt.update(() => B(p, T), !1, !0), wf(this.visualElement, "transform");
      const { animationState: j } = this.visualElement;
      j && j.setActive("whileDrag", !0);
    }, y = (p, T) => {
      this.latestPointerEvent = p, this.latestPanInfo = T;
      const { dragPropagation: V, dragDirectionLock: z, onDirectionLock: B, onDrag: j } = this.getProps();
      if (!V && !this.openDragLock)
        return;
      const { offset: L } = T;
      if (z && this.currentDirection === null) {
        this.currentDirection = QA(L), this.currentDirection !== null && B && B(this.currentDirection);
        return;
      }
      this.updateAxis("x", T.point, L), this.updateAxis("y", T.point, L), this.visualElement.render(), j && Vt.update(() => j(p, T), !1, !0);
    }, v = (p, T) => {
      this.latestPointerEvent = p, this.latestPanInfo = T, this.stop(p, T), this.latestPointerEvent = null, this.latestPanInfo = null;
    }, b = () => {
      const { dragSnapToOrigin: p } = this.getProps();
      (p || this.constraints) && this.startAnimation({ x: 0, y: 0 });
    }, { dragSnapToOrigin: g } = this.getProps();
    this.panSession = new e1(l, {
      onSessionStart: d,
      onStart: h,
      onMove: y,
      onSessionEnd: v,
      resumeAnimation: b
    }, {
      transformPagePoint: this.visualElement.getTransformPagePoint(),
      dragSnapToOrigin: g,
      distanceThreshold: o,
      contextWindow: t1(this.visualElement),
      element: this.visualElement.current
    });
  }
  /**
   * @internal
   */
  stop(l, r) {
    const o = l || this.latestPointerEvent, c = r || this.latestPanInfo, d = this.isDragging;
    if (this.cancel(), !d || !c || !o)
      return;
    const { velocity: h } = c;
    this.startAnimation(h);
    const { onDragEnd: y } = this.getProps();
    y && Vt.postRender(() => y(o, c));
  }
  /**
   * @internal
   */
  cancel() {
    this.isDragging = !1;
    const { projection: l, animationState: r } = this.visualElement;
    l && (l.isAnimationBlocked = !1), this.endPanSession();
    const { dragPropagation: o } = this.getProps();
    !o && this.openDragLock && (this.openDragLock(), this.openDragLock = null), r && r.setActive("whileDrag", !1);
  }
  /**
   * Clean up the pan session without modifying other drag state.
   * This is used during unmount to ensure event listeners are removed
   * without affecting projection animations or drag locks.
   * @internal
   */
  endPanSession() {
    this.panSession && this.panSession.end(), this.panSession = void 0;
  }
  updateAxis(l, r, o) {
    const { drag: c } = this.getProps();
    if (!o || !qu(l, c, this.currentDirection))
      return;
    const d = this.getAxisMotionValue(l);
    let h = this.originPoint[l] + o[l];
    this.constraints && this.constraints[l] && (h = jA(h, this.constraints[l], this.elastic[l])), d.set(h);
  }
  resolveConstraints() {
    const { dragConstraints: l, dragElastic: r } = this.getProps(), o = this.visualElement.projection && !this.visualElement.projection.layout ? this.visualElement.projection.measure(!1) : this.visualElement.projection?.layout, c = this.constraints;
    l && Xi(l) ? this.constraints || (this.constraints = this.resolveRefConstraints()) : l && o ? this.constraints = UA(o.layoutBox, l) : this.constraints = !1, this.elastic = YA(r), c !== this.constraints && !Xi(l) && o && this.constraints && !this.hasMutatedConstraints && Sn((d) => {
      this.constraints !== !1 && this.getAxisMotionValue(d) && (this.constraints[d] = LA(o.layoutBox[d], this.constraints[d]));
    });
  }
  resolveRefConstraints() {
    const { dragConstraints: l, onMeasureDragConstraints: r } = this.getProps();
    if (!l || !Xi(l))
      return !1;
    const o = l.current, { projection: c } = this.visualElement;
    if (!c || !c.layout)
      return !1;
    c.root && (c.root.scroll = void 0, c.root.updateScroll());
    const d = P2(o, c.root, this.visualElement.getTransformPagePoint());
    let h = BA(c.layout.layoutBox, d);
    if (r) {
      const y = r(K2(h));
      this.hasMutatedConstraints = !!y, y && (h = Av(y));
    }
    return h;
  }
  startAnimation(l) {
    const { drag: r, dragMomentum: o, dragElastic: c, dragTransition: d, dragSnapToOrigin: h, onDragTransitionEnd: y } = this.getProps(), v = this.constraints || {}, b = Sn((g) => {
      if (!qu(g, r, this.currentDirection))
        return;
      let p = v && v[g] || {};
      (h === !0 || h === g) && (p = { min: 0, max: 0 });
      const T = c ? 200 : 1e6, V = c ? 40 : 1e7, z = {
        type: "inertia",
        velocity: o ? l[g] : 0,
        bounceStiffness: T,
        bounceDamping: V,
        timeConstant: 750,
        restDelta: 1,
        restSpeed: 10,
        ...d,
        ...p
      };
      return this.startAxisValueAnimation(g, z);
    });
    return Promise.all(b).then(y);
  }
  startAxisValueAnimation(l, r) {
    const o = this.getAxisMotionValue(l);
    return wf(this.visualElement, l), o.start(uh(l, o, 0, r, this.visualElement, !1));
  }
  stopAnimation() {
    Sn((l) => this.getAxisMotionValue(l).stop());
  }
  /**
   * Drag works differently depending on which props are provided.
   *
   * - If _dragX and _dragY are provided, we output the gesture delta directly to those motion values.
   * - Otherwise, we apply the delta to the x/y motion values.
   */
  getAxisMotionValue(l) {
    const r = `_drag${l.toUpperCase()}`, c = this.visualElement.getProps()[r];
    return c || this.visualElement.getValue(l, this.visualElement.latestValues[l] ?? 0);
  }
  snapToCursor(l) {
    Sn((r) => {
      const { drag: o } = this.getProps();
      if (!qu(r, o, this.currentDirection))
        return;
      const { projection: c } = this.visualElement, d = this.getAxisMotionValue(r);
      if (c && c.layout) {
        const { min: h, max: y } = c.layout.layoutBox[r], v = d.get() || 0;
        d.set(l[r] - wt(h, y, 0.5) + v);
      }
    });
  }
  /**
   * When the viewport resizes we want to check if the measured constraints
   * have changed and, if so, reposition the element within those new constraints
   * relative to where it was before the resize.
   */
  scalePositionWithinConstraints() {
    if (!this.visualElement.current)
      return;
    const { drag: l, dragConstraints: r } = this.getProps(), { projection: o } = this.visualElement;
    if (!Xi(r) || !o || !this.constraints)
      return;
    this.stopAnimation();
    const c = { x: 0, y: 0 };
    Sn((h) => {
      const y = this.getAxisMotionValue(h);
      if (y && this.constraints !== !1) {
        const v = y.get();
        c[h] = HA({ min: v, max: v }, this.constraints[h]);
      }
    });
    const { transformTemplate: d } = this.visualElement.getProps();
    this.visualElement.current.style.transform = d ? d({}, "") : "none", o.root && o.root.updateScroll(), o.updateLayout(), this.constraints = !1, this.resolveConstraints(), Sn((h) => {
      if (!qu(h, l, null))
        return;
      const y = this.getAxisMotionValue(h), { min: v, max: b } = this.constraints[h];
      y.set(wt(v, b, c[h]));
    }), this.visualElement.render();
  }
  addListeners() {
    if (!this.visualElement.current)
      return;
    qA.set(this.visualElement, this);
    const l = this.visualElement.current, r = $l(l, "pointerdown", (b) => {
      const { drag: g, dragListener: p = !0 } = this.getProps(), T = b.target, V = T !== l && C2(T);
      g && p && !V && this.start(b);
    });
    let o;
    const c = () => {
      const { dragConstraints: b } = this.getProps();
      Xi(b) && b.current && (this.constraints = this.resolveRefConstraints(), o || (o = XA(l, b.current, () => this.scalePositionWithinConstraints())));
    }, { projection: d } = this.visualElement, h = d.addEventListener("measure", c);
    d && !d.layout && (d.root && d.root.updateScroll(), d.updateLayout()), Vt.read(c);
    const y = as(window, "resize", () => this.scalePositionWithinConstraints()), v = d.addEventListener("didUpdate", (({ delta: b, hasLayoutChanged: g }) => {
      this.isDragging && g && (Sn((p) => {
        const T = this.getAxisMotionValue(p);
        T && (this.originPoint[p] += b[p].translate, T.set(T.get() + b[p].translate));
      }), this.visualElement.render());
    }));
    return () => {
      y(), r(), h(), v && v(), o && o();
    };
  }
  getProps() {
    const l = this.visualElement.getProps(), { drag: r = !1, dragDirectionLock: o = !1, dragPropagation: c = !1, dragConstraints: d = !1, dragElastic: h = Gf, dragMomentum: y = !0 } = l;
    return {
      ...l,
      drag: r,
      dragDirectionLock: o,
      dragPropagation: c,
      dragConstraints: d,
      dragElastic: h,
      dragMomentum: y
    };
  }
}
function hg(i) {
  let l = !0;
  return () => {
    if (l) {
      l = !1;
      return;
    }
    i();
  };
}
function XA(i, l, r) {
  const o = T0(i, hg(r)), c = T0(l, hg(r));
  return () => {
    o(), c();
  };
}
function qu(i, l, r) {
  return (l === !0 || l === i) && (r === null || r === i);
}
function QA(i, l = 10) {
  let r = null;
  return Math.abs(i.y) > l ? r = "y" : Math.abs(i.x) > l && (r = "x"), r;
}
class ZA extends ba {
  constructor(l) {
    super(l), this.removeGroupControls = Pe, this.removeListeners = Pe, this.controls = new GA(l);
  }
  mount() {
    const { dragControls: l } = this.node.getProps();
    l && (this.removeGroupControls = l.subscribe(this.controls)), this.removeListeners = this.controls.addListeners() || Pe;
  }
  update() {
    const { dragControls: l } = this.node.getProps(), { dragControls: r } = this.node.prevProps || {};
    l !== r && (this.removeGroupControls(), l && (this.removeGroupControls = l.subscribe(this.controls)));
  }
  unmount() {
    this.removeGroupControls(), this.removeListeners(), this.controls.isDragging || this.controls.endPanSession();
  }
}
const yf = (i) => (l, r) => {
  i && Vt.update(() => i(l, r), !1, !0);
};
class KA extends ba {
  constructor() {
    super(...arguments), this.removePointerDownListener = Pe;
  }
  onPointerDown(l) {
    this.session = new e1(l, this.createPanHandlers(), {
      transformPagePoint: this.node.getTransformPagePoint(),
      contextWindow: t1(this.node)
    });
  }
  createPanHandlers() {
    const { onPanSessionStart: l, onPanStart: r, onPan: o, onPanEnd: c } = this.node.getProps();
    return {
      onSessionStart: yf(l),
      onStart: yf(r),
      onMove: yf(o),
      onEnd: (d, h) => {
        delete this.session, c && Vt.postRender(() => c(d, h));
      }
    };
  }
  mount() {
    this.removePointerDownListener = $l(this.node.current, "pointerdown", (l) => this.onPointerDown(l));
  }
  update() {
    this.session && this.session.updateHandlers(this.createPanHandlers());
  }
  unmount() {
    this.removePointerDownListener(), this.session && this.session.end();
  }
}
let pf = !1;
class JA extends K.Component {
  /**
   * This only mounts projection nodes for components that
   * need measuring, we might want to do it for all components
   * in order to incorporate transforms
   */
  componentDidMount() {
    const { visualElement: l, layoutGroup: r, switchLayoutGroup: o, layoutId: c } = this.props, { projection: d } = l;
    d && (r.group && r.group.add(d), o && o.register && c && o.register(d), pf && d.root.didUpdate(), d.addEventListener("animationComplete", () => {
      this.safeToRemove();
    }), d.setOptions({
      ...d.options,
      layoutDependency: this.props.layoutDependency,
      onExitComplete: () => this.safeToRemove()
    })), Pu.hasEverUpdated = !0;
  }
  getSnapshotBeforeUpdate(l) {
    const { layoutDependency: r, visualElement: o, drag: c, isPresent: d } = this.props, { projection: h } = o;
    return h && (h.isPresent = d, l.layoutDependency !== r && h.setOptions({
      ...h.options,
      layoutDependency: r
    }), pf = !0, c || l.layoutDependency !== r || r === void 0 || l.isPresent !== d ? h.willUpdate() : this.safeToRemove(), l.isPresent !== d && (d ? h.promote() : h.relegate() || Vt.postRender(() => {
      const y = h.getStack();
      (!y || !y.members.length) && this.safeToRemove();
    }))), null;
  }
  componentDidUpdate() {
    const { visualElement: l, layoutAnchor: r } = this.props, { projection: o } = l;
    o && (o.options.layoutAnchor = r, o.root.didUpdate(), fh.postRender(() => {
      !o.currentAnimation && o.isLead() && this.safeToRemove();
    }));
  }
  componentWillUnmount() {
    const { visualElement: l, layoutGroup: r, switchLayoutGroup: o } = this.props, { projection: c } = l;
    pf = !0, c && (c.scheduleCheckAfterUnmount(), r && r.group && r.group.remove(c), o && o.deregister && o.deregister(c));
  }
  safeToRemove() {
    const { safeToRemove: l } = this.props;
    l && l();
  }
  render() {
    return null;
  }
}
function a1(i) {
  const [l, r] = tA(), o = K.useContext(Sg);
  return R.jsx(JA, { ...i, layoutGroup: o, switchLayoutGroup: K.useContext(Iv), isPresent: l, safeToRemove: r });
}
const kA = {
  pan: {
    Feature: KA
  },
  drag: {
    Feature: ZA,
    ProjectionNode: Qv,
    MeasureLayout: a1
  }
};
function dg(i, l, r) {
  const { props: o } = i;
  i.animationState && o.whileHover && i.animationState.setActive("whileHover", r === "Start");
  const c = "onHover" + r, d = o[c];
  d && Vt.postRender(() => d(l, us(l)));
}
class PA extends ba {
  mount() {
    const { current: l } = this.node;
    l && (this.unmount = E2(l, (r, o) => (dg(this.node, o, "Start"), (c) => dg(this.node, c, "End"))));
  }
  unmount() {
  }
}
class FA extends ba {
  constructor() {
    super(...arguments), this.isActive = !1;
  }
  onFocus() {
    let l = !1;
    try {
      l = this.node.current.matches(":focus-visible");
    } catch {
      l = !0;
    }
    !l || !this.node.animationState || (this.node.animationState.setActive("whileFocus", !0), this.isActive = !0);
  }
  onBlur() {
    !this.isActive || !this.node.animationState || (this.node.animationState.setActive("whileFocus", !1), this.isActive = !1);
  }
  mount() {
    this.unmount = is(as(this.node.current, "focus", () => this.onFocus()), as(this.node.current, "blur", () => this.onBlur()));
  }
  unmount() {
  }
}
function mg(i, l, r) {
  const { props: o } = i;
  if (i.current instanceof HTMLButtonElement && i.current.disabled)
    return;
  i.animationState && o.whileTap && i.animationState.setActive("whileTap", r === "Start");
  const c = "onTap" + (r === "End" ? "" : r), d = o[c];
  d && Vt.postRender(() => d(l, us(l)));
}
class WA extends ba {
  mount() {
    const { current: l } = this.node;
    if (!l)
      return;
    const { globalTapTarget: r, propagate: o } = this.node.props;
    this.unmount = N2(l, (c, d) => (mg(this.node, d, "Start"), (h, { success: y }) => mg(this.node, h, y ? "End" : "Cancel")), {
      useGlobalTarget: r,
      stopPropagation: o?.tap === !1
    });
  }
  unmount() {
  }
}
const Xf = /* @__PURE__ */ new WeakMap(), gf = /* @__PURE__ */ new WeakMap(), IA = (i) => {
  const l = Xf.get(i.target);
  l && l(i);
}, $A = (i) => {
  i.forEach(IA);
};
function t3({ root: i, ...l }) {
  const r = i || document;
  gf.has(r) || gf.set(r, {});
  const o = gf.get(r), c = JSON.stringify(l);
  return o[c] || (o[c] = new IntersectionObserver($A, { root: i, ...l })), o[c];
}
function e3(i, l, r) {
  const o = t3(l);
  return Xf.set(i, r), o.observe(i), () => {
    Xf.delete(i), o.unobserve(i);
  };
}
const n3 = {
  some: 0,
  all: 1
};
class a3 extends ba {
  constructor() {
    super(...arguments), this.hasEnteredView = !1, this.isInView = !1;
  }
  startObserver() {
    this.stopObserver?.();
    const { viewport: l = {} } = this.node.getProps(), { root: r, margin: o, amount: c = "some", once: d } = l, h = {
      root: r ? r.current : void 0,
      rootMargin: o,
      threshold: typeof c == "number" ? c : n3[c]
    }, y = (v) => {
      const { isIntersecting: b } = v;
      if (this.isInView === b || (this.isInView = b, d && !b && this.hasEnteredView))
        return;
      b && (this.hasEnteredView = !0), this.node.animationState && this.node.animationState.setActive("whileInView", b);
      const { onViewportEnter: g, onViewportLeave: p } = this.node.getProps(), T = b ? g : p;
      T && T(v);
    };
    this.stopObserver = e3(this.node.current, h, y);
  }
  mount() {
    this.startObserver();
  }
  update() {
    if (typeof IntersectionObserver > "u")
      return;
    const { props: l, prevProps: r } = this.node;
    ["amount", "margin", "root"].some(i3(l, r)) && this.startObserver();
  }
  unmount() {
    this.stopObserver?.(), this.hasEnteredView = !1, this.isInView = !1;
  }
}
function i3({ viewport: i = {} }, { viewport: l = {} } = {}) {
  return (r) => i[r] !== l[r];
}
const l3 = {
  inView: {
    Feature: a3
  },
  tap: {
    Feature: WA
  },
  focus: {
    Feature: FA
  },
  hover: {
    Feature: PA
  }
}, s3 = {
  layout: {
    ProjectionNode: Qv,
    MeasureLayout: a1
  }
}, u3 = {
  ...zA,
  ...l3,
  ...kA,
  ...s3
}, o3 = /* @__PURE__ */ MA(u3, DA);
function r3() {
  !ph.current && Tv();
  const [i] = K.useState(no.current);
  return i;
}
const Ja = o3;
const c3 = (i) => i.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase(), f3 = (i) => i.replace(
  /^([A-Z])|[\s-_]+(\w)/g,
  (l, r, o) => o ? o.toUpperCase() : r.toLowerCase()
), yg = (i) => {
  const l = f3(i);
  return l.charAt(0).toUpperCase() + l.slice(1);
}, i1 = (...i) => i.filter((l, r, o) => !!l && l.trim() !== "" && o.indexOf(l) === r).join(" ").trim(), h3 = (i) => {
  for (const l in i)
    if (l.startsWith("aria-") || l === "role" || l === "title")
      return !0;
};
var d3 = {
  xmlns: "http://www.w3.org/2000/svg",
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round"
};
const m3 = K.forwardRef(
  ({
    color: i = "currentColor",
    size: l = 24,
    strokeWidth: r = 2,
    absoluteStrokeWidth: o,
    className: c = "",
    children: d,
    iconNode: h,
    ...y
  }, v) => K.createElement(
    "svg",
    {
      ref: v,
      ...d3,
      width: l,
      height: l,
      stroke: i,
      strokeWidth: o ? Number(r) * 24 / Number(l) : r,
      className: i1("lucide", c),
      ...!d && !h3(y) && { "aria-hidden": "true" },
      ...y
    },
    [
      ...h.map(([b, g]) => K.createElement(b, g)),
      ...Array.isArray(d) ? d : [d]
    ]
  )
);
const Sa = (i, l) => {
  const r = K.forwardRef(
    ({ className: o, ...c }, d) => K.createElement(m3, {
      ref: d,
      iconNode: l,
      className: i1(
        `lucide-${c3(yg(i))}`,
        `lucide-${i}`,
        o
      ),
      ...c
    })
  );
  return r.displayName = yg(i), r;
};
const y3 = [
  ["path", { d: "M5 12h14", key: "1ays0h" }],
  ["path", { d: "m12 5 7 7-7 7", key: "xquz4c" }]
], p3 = Sa("arrow-right", y3);
const g3 = [
  ["path", { d: "M7 7h10v10", key: "1tivn9" }],
  ["path", { d: "M7 17 17 7", key: "1vkiza" }]
], Qf = Sa("arrow-up-right", g3);
const v3 = [
  ["path", { d: "M8 2v4", key: "1cmpym" }],
  ["path", { d: "M16 2v4", key: "4m81vk" }],
  ["rect", { width: "18", height: "18", x: "3", y: "4", rx: "2", key: "1hopcy" }],
  ["path", { d: "M3 10h18", key: "8toen8" }],
  ["path", { d: "M8 14h.01", key: "6423bh" }],
  ["path", { d: "M12 14h.01", key: "1etili" }],
  ["path", { d: "M16 14h.01", key: "1gbofw" }],
  ["path", { d: "M8 18h.01", key: "lrp35t" }],
  ["path", { d: "M12 18h.01", key: "mhygvu" }],
  ["path", { d: "M16 18h.01", key: "kzsmim" }]
], b3 = Sa("calendar-days", v3);
const S3 = [
  [
    "path",
    { d: "m21 8-2 2-1.5-3.7A2 2 0 0 0 15.646 5H8.4a2 2 0 0 0-1.903 1.257L5 10 3 8", key: "1imjwt" }
  ],
  ["path", { d: "M7 14h.01", key: "1qa3f1" }],
  ["path", { d: "M17 14h.01", key: "7oqj8z" }],
  ["rect", { width: "18", height: "8", x: "3", y: "10", rx: "2", key: "a7itu8" }],
  ["path", { d: "M5 18v2", key: "ppbyun" }],
  ["path", { d: "M19 18v2", key: "gy7782" }]
], Zf = Sa("car-front", S3);
const T3 = [
  [
    "path",
    {
      d: "m16.24 7.76-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z",
      key: "9ktpf1"
    }
  ],
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }]
], x3 = Sa("compass", T3);
const E3 = [
  ["path", { d: "M3 7V5a2 2 0 0 1 2-2h2", key: "aa7l1z" }],
  ["path", { d: "M17 3h2a2 2 0 0 1 2 2v2", key: "4qcy5o" }],
  ["path", { d: "M21 17v2a2 2 0 0 1-2 2h-2", key: "6vwrx8" }],
  ["path", { d: "M7 21H5a2 2 0 0 1-2-2v-2", key: "ioqczr" }],
  ["path", { d: "M7 12h10", key: "b7w52i" }]
], l1 = Sa("scan-line", E3);
const A3 = [
  [
    "path",
    {
      d: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
      key: "oel41y"
    }
  ],
  ["path", { d: "m9 12 2 2 4-4", key: "dzmm74" }]
], M3 = Sa("shield-check", A3);
const D3 = [
  [
    "path",
    {
      d: "M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z",
      key: "1s2grr"
    }
  ],
  ["path", { d: "M20 2v4", key: "1rf3ol" }],
  ["path", { d: "M22 4h-4", key: "gwowj6" }],
  ["circle", { cx: "4", cy: "20", r: "2", key: "6kqj1y" }]
], C3 = Sa("sparkles", D3), O3 = sT.lazy(() => import("./yard-ShowroomScene-BEKSahzV.js"));
function pg({ reduce: i }) {
  const l = K.useId().replace(/:/g, "");
  return /* @__PURE__ */ R.jsxs("svg", { "aria-hidden": "true", className: "pointer-events-none absolute inset-0 h-full w-full opacity-50", viewBox: "0 0 800 600", preserveAspectRatio: "xMidYMid slice", children: [
    /* @__PURE__ */ R.jsx("defs", { children: /* @__PURE__ */ R.jsx("pattern", { id: l, width: "70", height: "70", patternUnits: "userSpaceOnUse", children: /* @__PURE__ */ R.jsx("path", { d: "M70 0H0V70", stroke: "#80b5be", strokeOpacity: ".17", fill: "none", strokeWidth: ".7" }) }) }),
    /* @__PURE__ */ R.jsx("rect", { width: "800", height: "600", fill: "url(#" + l + ")" }),
    Array.from({ length: 10 }, (r, o) => /* @__PURE__ */ R.jsx(
      Ja.rect,
      {
        x: (o * 127 + 70) % 750,
        y: (o * 79 + 80) % 550,
        width: "70",
        height: "70",
        fill: "#b4dce4",
        initial: { opacity: 0.025 },
        animate: i ? { opacity: 0.04 } : { opacity: [0.02, 0.14, 0.02] },
        transition: { duration: 4.2, delay: o * 0.42, repeat: i ? 0 : 1 / 0, ease: "easeInOut" }
      },
      o
    ))
  ] });
}
class N3 extends K.Component {
  constructor(l) {
    super(l), this.state = { failed: !1 };
  }
  static getDerivedStateFromError() {
    return { failed: !0 };
  }
  render() {
    return this.state.failed ? /* @__PURE__ */ R.jsx(Kf, {}) : this.props.children;
  }
}
function Kf({ launch3D: i }) {
  return /* @__PURE__ */ R.jsxs("div", { "data-3d-fallback": "true", className: "flex h-full w-full flex-col items-center justify-center gap-5 bg-[radial-gradient(ellipse_at_center,#294b56_0%,#102631_62%,#061823_100%)] px-5", children: [
    /* @__PURE__ */ R.jsx(Zf, { className: "h-24 w-24 text-[#d2b77d]/90 sm:h-32 sm:w-32", strokeWidth: 0.65, "aria-hidden": "true" }),
    /* @__PURE__ */ R.jsx("span", { className: "text-center text-[10px] font-semibold uppercase tracking-[.29em] text-slate-300", children: "Interactive showroom concept" }),
    i && /* @__PURE__ */ R.jsx(
      "button",
      {
        type: "button",
        "data-launch-3d": "true",
        onClick: i,
        "aria-label": "Load interactive 3D vehicle showroom",
        className: "relative z-20 min-h-12 rounded-md border border-[#dfbd82] bg-[#dfbd82] px-6 py-3 text-[11px] font-extrabold uppercase tracking-[.13em] text-[#10232b] transition-colors hover:bg-[#f2d8a9] focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-white",
        children: "Explore in 3D"
      }
    )
  ] });
}
const gg = [
  { id: "three-quarter", name: "Three-quarter" },
  { id: "side", name: "Side profile" },
  { id: "front", name: "Front detail" }
], vf = [
  { id: "ocean", name: "Ocean teal", body: "#1a3d46", roof: "#203c48", swatch: "bg-[#1a3d46]" },
  { id: "champagne", name: "Champagne gold", body: "#9b8057", roof: "#b19b76", swatch: "bg-[#9b8057]" },
  { id: "silver", name: "Arctic silver", body: "#7f9aa9", roof: "#9fb1ba", swatch: "bg-[#7f9aa9]" }
];
function z3({ reduce: i }) {
  const l = K.useRef(null), [r, o] = K.useState(!1), [c, d] = K.useState(!0), [h, y] = K.useState(!1), [v, b] = K.useState(!1), [g, p] = K.useState(!1), [T, V] = K.useState("three-quarter"), [z, B] = K.useState("ocean"), j = vf.find((U) => U.id === z) || vf[0];
  K.useEffect(() => {
    const U = window.matchMedia("(max-width: 640px) and (pointer: coarse)"), G = () => b(U.matches);
    return G(), U.addEventListener?.("change", G), () => U.removeEventListener?.("change", G);
  }, []), K.useEffect(() => {
    const U = l.current;
    if (!U) return;
    const G = () => d(document.visibilityState === "visible");
    if (G(), document.addEventListener("visibilitychange", G), !("IntersectionObserver" in window)) o(!0);
    else {
      const nt = new IntersectionObserver(([rt]) => {
        o(rt.isIntersecting);
      }, { rootMargin: "100px 0px", threshold: 0.01 });
      return nt.observe(U), () => {
        nt.disconnect(), document.removeEventListener("visibilitychange", G);
      };
    }
    return () => document.removeEventListener("visibilitychange", G);
  }, []), K.useEffect(() => {
    if (!(!r || !c || i || v && !g))
      try {
        const U = document.createElement("canvas"), G = U.getContext("webgl2") || U.getContext("webgl");
        y(!!G), G && G.getExtension("WEBGL_lose_context")?.loseContext();
      } catch {
        y(!1);
      }
  }, [r, c, i, v, g]);
  const L = v && !g, Y = h && r && c && !i && !L;
  return /* @__PURE__ */ R.jsxs("div", { ref: l, "data-showroom-active": Y ? "true" : "false", className: "w-full", children: [
    /* @__PURE__ */ R.jsxs("div", { className: "relative isolate h-[300px] w-full overflow-hidden rounded-t-2xl border border-white/10 bg-[#102630] shadow-[0_28px_90px_rgba(0,0,0,.45)] sm:h-[400px] lg:h-[510px]", children: [
      Y ? /* @__PURE__ */ R.jsx(N3, { children: /* @__PURE__ */ R.jsx(K.Suspense, { fallback: /* @__PURE__ */ R.jsx(Kf, {}), children: /* @__PURE__ */ R.jsx(O3, { motionAllowed: Y, view: T, paint: j }) }) }) : /* @__PURE__ */ R.jsx(Kf, { launch3D: L && !i ? () => p(!0) : void 0 }),
      /* @__PURE__ */ R.jsxs("div", { className: "pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 p-4 sm:p-7", children: [
        /* @__PURE__ */ R.jsx("span", { className: "rounded-full border border-white/25 bg-[#102630]/80 px-3 py-2 text-[9px] font-bold uppercase tracking-[.23em] text-[#e2cc9a] backdrop-blur-md", children: "3D Concept Studio" }),
        /* @__PURE__ */ R.jsx("span", { className: "rounded-full border border-white/15 bg-black/25 px-3 py-2 text-[9px] font-semibold tracking-[.12em] text-slate-300 backdrop-blur-md", children: Y ? "LIVE / EXPLORE" : "VISUAL / PREVIEW" })
      ] }),
      /* @__PURE__ */ R.jsxs("div", { className: "pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-[#07141d] via-[#07141d]/75 to-transparent px-4 pb-4 pt-10 sm:px-7 sm:pb-6", children: [
        /* @__PURE__ */ R.jsxs("span", { className: "flex items-center gap-2 text-[10px] font-semibold tracking-[.13em] text-slate-200", children: [
          /* @__PURE__ */ R.jsx(l1, { className: "h-4 w-4 text-[#d6b579]" }),
          " Procedural vehicle geometry"
        ] }),
        /* @__PURE__ */ R.jsx("span", { className: "text-[9px] font-bold uppercase tracking-[.16em] text-[#b6c5ca]", children: "No external model" })
      ] })
    ] }),
    /* @__PURE__ */ R.jsxs("div", { className: "grid gap-4 rounded-b-2xl border border-t-0 border-white/15 bg-[#0c202a] px-4 py-4 sm:grid-cols-[1fr_auto] sm:items-center sm:px-6", children: [
      /* @__PURE__ */ R.jsx("div", { role: "group", "aria-label": "Showroom camera view", className: "flex flex-wrap items-center gap-2", children: gg.map((U) => /* @__PURE__ */ R.jsx(
        "button",
        {
          type: "button",
          "data-camera-view": U.id,
          "aria-pressed": T === U.id,
          onClick: () => V(U.id),
          className: "min-h-10 rounded-md border px-3 py-2 text-[10px] font-semibold tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#dfbd82] " + (T === U.id ? "border-[#d6b579] bg-[#d6b579] text-[#0b1e28]" : "border-white/20 bg-white/5 text-slate-200 hover:border-white/50"),
          children: U.name
        },
        U.id
      )) }),
      /* @__PURE__ */ R.jsx("div", { role: "group", "aria-label": "Fictional vehicle paint finish", className: "flex items-center gap-2", children: vf.map((U) => /* @__PURE__ */ R.jsx(
        "button",
        {
          type: "button",
          "data-paint-finish": U.id,
          "aria-label": U.name,
          "aria-pressed": z === U.id,
          title: U.name,
          onClick: () => B(U.id),
          className: "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#dfbd82] " + (z === U.id ? "border-[#e8c791]" : "border-white/20 hover:border-white/60"),
          children: /* @__PURE__ */ R.jsx("span", { className: "h-6 w-6 rounded-full border border-white/30 " + U.swatch, "aria-hidden": "true" })
        },
        U.id
      )) })
    ] }),
    /* @__PURE__ */ R.jsxs("p", { className: "sr-only", role: "status", children: [
      "Showroom view: ",
      gg.find((U) => U.id === T)?.name,
      ". Concept paint: ",
      j.name,
      ".",
      i ? " Motion reduced." : ""
    ] })
  ] });
}
const vg = Object.freeze({
  name: "Atelier Motors",
  strapline: "Showroom concept",
  eyebrow: "The future of the showroom",
  headline: "Drive something",
  highlight: "extraordinary.",
  description: "An immersive WordPress dealership concept with cinematic 3D, refined inventory discovery, and a governed service-workshop foundation.",
  contact_label: "Enquiry info",
  contact_path: "/contact/",
  accent: "gold"
}), uo = {
  gold: {
    notice: "bg-[#dfbd82]",
    logo: "text-[#dbbc88]",
    highlight: "text-[#dcbc85]",
    eyebrow: "text-[#dcbc85]",
    primary: "bg-[#dfbd82] text-[#11232b] hover:bg-[#f2d8a9]",
    border: "border-[#dfbd82]/70",
    muted: "text-[#e6c691]"
  },
  ice: {
    notice: "bg-[#b6ddeb]",
    logo: "text-[#b6ddeb]",
    highlight: "text-[#b6ddeb]",
    eyebrow: "text-[#b6ddeb]",
    primary: "bg-[#b6ddeb] text-[#11232b] hover:bg-[#d1eefa]",
    border: "border-[#b6ddeb]/70",
    muted: "text-[#d1eefa]"
  },
  copper: {
    notice: "bg-[#dca87c]",
    logo: "text-[#dca87c]",
    highlight: "text-[#dca87c]",
    eyebrow: "text-[#dca87c]",
    primary: "bg-[#dca87c] text-[#11232b] hover:bg-[#f1c7a4]",
    border: "border-[#dca87c]/70",
    muted: "text-[#f1c7a4]"
  }
};
function R3() {
  try {
    const i = document.getElementById("empire-yard-brand-settings")?.textContent, l = i ? JSON.parse(i) : {}, r = { ...vg };
    for (const o of [
      "name",
      "strapline",
      "eyebrow",
      "headline",
      "highlight",
      "description",
      "contact_label"
    ])
      typeof l[o] == "string" && l[o].trim() && (r[o] = l[o].slice(0, 320));
    return typeof l.contact_path == "string" && /^\/(?:[a-z0-9-]+\/){1,4}$/.test(l.contact_path) && (r.contact_path = l.contact_path), Object.prototype.hasOwnProperty.call(uo, l.accent) && (r.accent = l.accent), r;
  } catch {
    return vg;
  }
}
function bf({ children: i, href: l, primary: r = !1, palette: o = uo.gold }) {
  return /* @__PURE__ */ R.jsxs("a", { href: l, className: (r ? o.primary : "border border-white/30 bg-white/5 text-white hover:bg-white/10") + " inline-flex min-h-12 items-center justify-center gap-3 rounded-md px-6 py-3 text-xs font-extrabold uppercase tracking-[.11em] no-underline transition-colors focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-[#eecb87]", children: [
    i,
    /* @__PURE__ */ R.jsx(Qf, { "aria-hidden": "true", className: "h-4 w-4" })
  ] });
}
const _3 = [
  { num: "01", icon: x3, title: "Discovery, refined.", copy: "Fictional showroom inventory with clear filters and a responsive presentation. Real stock feeds need client authorisation." },
  { num: "02", icon: l1, title: "Details worth exploring.", copy: "Honest model specifications and image spaces without fabricated availability, reviews or pricing claims." },
  { num: "03", icon: b3, title: "A smarter workshop.", copy: "The private workbench uses database-backed slot protection. Customer booking remains disabled." }
], w3 = [
  { num: "I", name: "Grand Tourer", colors: "from-[#2b4c57] via-[#122d39] to-[#061b27]" },
  { num: "II", name: "Urban Explorer", colors: "from-[#aa9471] via-[#5f655e] to-[#152d34]" },
  { num: "III", name: "Electric Era", colors: "from-[#436b71] via-[#2b414a] to-[#101a26]" }
];
function V3() {
  const i = !!r3(), [l, r] = K.useState(!1), o = i || window.matchMedia("(max-width: 640px)").matches ? !1 : { opacity: 0, y: 22 }, c = R3(), d = uo[c.accent] || uo.gold;
  return /* @__PURE__ */ R.jsxs("div", { "data-react-showroom": "true", "data-brand-accent": c.accent, className: "min-h-screen bg-[#f5f2eb] font-sans text-[#0b1e28] antialiased", children: [
    /* @__PURE__ */ R.jsx("a", { href: "#main", className: "sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-white focus:p-3 focus:text-black", children: "Skip to main content" }),
    /* @__PURE__ */ R.jsx("div", { className: d.notice + " px-4 py-2 text-center text-[9px] font-black uppercase tracking-[.2em] text-[#17303b] sm:text-[10px]", children: /* @__PURE__ */ R.jsxs("span", { className: "inline-flex items-center gap-2", children: [
      /* @__PURE__ */ R.jsx(M3, { className: "h-3.5 w-3.5", "aria-hidden": "true" }),
      " Fictional design preview — no live dealership, prices or bookings"
    ] }) }),
    /* @__PURE__ */ R.jsx("header", { className: "relative z-30 border-b border-white/10 bg-[#091923] text-white", children: /* @__PURE__ */ R.jsxs("nav", { "aria-label": "Primary navigation", className: "mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-4 px-5 py-5 md:px-10 lg:py-6", children: [
      /* @__PURE__ */ R.jsxs("a", { href: "/", className: "inline-flex items-center gap-3 no-underline", "aria-label": c.name + " concept home", children: [
        /* @__PURE__ */ R.jsx("span", { className: "flex h-10 w-10 items-center justify-center rounded-full border border-[#ddb982]/65 text-[#ddb982]", children: /* @__PURE__ */ R.jsx(Zf, { className: "h-6 w-6", strokeWidth: 1.3 }) }),
        /* @__PURE__ */ R.jsxs("span", { className: "text-[15px] font-black tracking-[.18em] text-white", children: [
          c.name.toUpperCase(),
          /* @__PURE__ */ R.jsx("span", { className: "mt-0.5 block text-[8px] tracking-[.32em] " + d.logo, children: c.strapline.toUpperCase() })
        ] })
      ] }),
      /* @__PURE__ */ R.jsx("button", { "aria-label": l ? "Close navigation" : "Open navigation", "aria-expanded": l, onClick: () => r(!l), className: "rounded border border-white/30 px-3 py-2 text-[11px] uppercase tracking-widest text-white md:hidden", children: l ? "Close" : "Menu" }),
      /* @__PURE__ */ R.jsxs("div", { className: (l ? "flex" : "hidden") + " w-full flex-col gap-5 md:flex md:w-auto md:flex-row md:items-center md:gap-9", children: [
        [["The studio", "#studio"], ["The collection", "#collection"], ["Experience", "#experience"], ["Inventory", "/demo-stock/"]].map(
          ([h, y]) => /* @__PURE__ */ R.jsx("a", { href: y, className: "text-[11px] font-bold uppercase tracking-[.14em] text-[#d4e0e3] no-underline hover:text-[#dfbd82]", children: h }, h)
        ),
        /* @__PURE__ */ R.jsxs("a", { href: c.contact_path, className: "inline-flex min-h-10 items-center justify-center gap-2 rounded border border-white/30 px-4 py-2 text-[10px] font-black uppercase tracking-[.12em] text-[#e6c691] no-underline hover:bg-white/10", children: [
          c.contact_label,
          " ",
          /* @__PURE__ */ R.jsx(Qf, { className: "h-4 w-4" })
        ] })
      ] })
    ] }) }),
    /* @__PURE__ */ R.jsxs("main", { id: "main", children: [
      /* @__PURE__ */ R.jsxs("section", { id: "studio", "aria-labelledby": "studio-title", className: "relative isolate overflow-hidden bg-[#091923] text-white", children: [
        /* @__PURE__ */ R.jsx(pg, { reduce: i }),
        /* @__PURE__ */ R.jsx("div", { className: "pointer-events-none absolute -left-60 top-[-150px] h-[600px] w-[600px] rounded-full bg-[#22505a]/35 blur-[135px]" }),
        /* @__PURE__ */ R.jsxs("div", { className: "relative mx-auto grid max-w-[1320px] items-center gap-12 px-5 pb-10 pt-16 md:px-10 lg:min-h-[720px] lg:grid-cols-[.91fr_1.09fr] lg:gap-7 lg:pb-20 lg:pt-20", children: [
          /* @__PURE__ */ R.jsxs("div", { className: "relative z-10 max-w-[610px]", children: [
            /* @__PURE__ */ R.jsxs(Ja.p, { initial: o, animate: { opacity: 1, y: 0 }, transition: { delay: 0.05 }, className: "mb-6 inline-flex items-center gap-3 text-[10px] font-black uppercase tracking-[.27em] " + d.eyebrow, children: [
              /* @__PURE__ */ R.jsx("span", { className: "h-px w-8 bg-current" }),
              " ",
              c.eyebrow
            ] }),
            /* @__PURE__ */ R.jsxs(Ja.h1, { id: "studio-title", initial: o, animate: { opacity: 1, y: 0 }, transition: { duration: 0.7, delay: 0.12 }, className: "max-w-[11ch] font-serif text-[clamp(3.4rem,6vw,5.6rem)] leading-[.92] tracking-[-.068em] text-[#fffdf7]", children: [
              c.headline,
              " ",
              /* @__PURE__ */ R.jsx("em", { className: "font-normal " + d.highlight, children: c.highlight })
            ] }),
            /* @__PURE__ */ R.jsx(Ja.p, { initial: o, animate: { opacity: 1, y: 0 }, transition: { delay: 0.22 }, className: "mb-8 mt-7 max-w-[50ch] text-[15px] leading-[1.85] text-[#bacbd2] sm:text-base", children: c.description }),
            /* @__PURE__ */ R.jsxs(Ja.div, { initial: o, animate: { opacity: 1, y: 0 }, transition: { delay: 0.3 }, className: "flex flex-wrap gap-3", children: [
              /* @__PURE__ */ R.jsx(bf, { primary: !0, palette: d, href: "/demo-stock/", children: "Explore fictional stock" }),
              /* @__PURE__ */ R.jsx(bf, { href: "#experience", children: "Discover the concept" })
            ] }),
            /* @__PURE__ */ R.jsxs("div", { className: "mt-10 flex flex-wrap items-center gap-5 border-t border-white/15 pt-5 text-[10px] uppercase tracking-[.14em] text-[#aabdc4]", children: [
              /* @__PURE__ */ R.jsxs("span", { className: "inline-flex items-center gap-2", children: [
                /* @__PURE__ */ R.jsx(C3, { className: "h-4 w-4 text-[#dcbc85]" }),
                " React + Three.js"
              ] }),
              /* @__PURE__ */ R.jsx("span", { children: "Mobile-first" }),
              /* @__PURE__ */ R.jsx("span", { children: "WordPress native" })
            ] })
          ] }),
          /* @__PURE__ */ R.jsxs(Ja.div, { initial: o === !1 ? !1 : { opacity: 0, x: 28 }, animate: { opacity: 1, x: 0 }, transition: { duration: 0.9, delay: 0.1 }, className: "relative z-10", children: [
            /* @__PURE__ */ R.jsx(z3, { reduce: i }),
            /* @__PURE__ */ R.jsx("p", { className: "mt-3 text-center text-[10px] font-semibold uppercase tracking-[.15em] text-[#899da5]", children: "Illustrative 3D geometry — no real manufacturer design" })
          ] })
        ] }),
        /* @__PURE__ */ R.jsx("div", { className: "relative border-t border-white/10 bg-black/20", children: /* @__PURE__ */ R.jsxs("div", { className: "mx-auto flex max-w-[1320px] flex-wrap justify-between gap-3 px-5 py-5 text-[10px] font-semibold uppercase tracking-[.18em] text-[#b4c8ce] md:px-10", children: [
          /* @__PURE__ */ R.jsx("span", { children: "01 — A digital showroom" }),
          /* @__PURE__ */ R.jsx("span", { children: "02 — Evidence-led inventory" }),
          /* @__PURE__ */ R.jsx("span", { children: "03 — Private workshop intelligence" })
        ] }) })
      ] }),
      /* @__PURE__ */ R.jsx("section", { id: "experience", className: "bg-[#f5f2eb] px-5 py-20 md:px-10 md:py-28", children: /* @__PURE__ */ R.jsxs("div", { className: "mx-auto max-w-[1240px]", children: [
        /* @__PURE__ */ R.jsxs("div", { className: "mb-12 grid items-end gap-7 lg:grid-cols-[1.05fr_.95fr]", children: [
          /* @__PURE__ */ R.jsxs("div", { children: [
            /* @__PURE__ */ R.jsx("p", { className: "mb-3 text-[11px] font-extrabold uppercase tracking-[.22em] text-[#916d3b]", children: "Luxury in every interaction" }),
            /* @__PURE__ */ R.jsxs("h2", { className: "max-w-[15ch] font-serif text-[clamp(2.9rem,5vw,5.1rem)] leading-[1.08] tracking-[-.06em]", children: [
              "Built to make an ",
              /* @__PURE__ */ R.jsx("em", { children: "impression." })
            ] })
          ] }),
          /* @__PURE__ */ R.jsx("p", { className: "max-w-[55ch] text-base leading-[1.9] text-[#596a71]", children: "A dealership website should feel as considered as the vehicles it presents. This demo connects visual polish to practical administration without pretending a customer has gone live." })
        ] }),
        /* @__PURE__ */ R.jsx("div", { className: "grid gap-4 md:grid-cols-3", children: _3.map(({ num: h, icon: y, title: v, copy: b }) => /* @__PURE__ */ R.jsxs(Ja.article, { whileHover: i ? void 0 : { y: -5 }, className: "flex min-h-[310px] flex-col rounded-lg border border-[#dce2df] bg-white p-7 shadow-[0_22px_55px_rgba(8,25,35,.035)] sm:p-9", children: [
          /* @__PURE__ */ R.jsxs("div", { className: "mb-auto flex items-start justify-between", children: [
            /* @__PURE__ */ R.jsx("span", { className: "text-xs font-extrabold tracking-[.24em] text-[#b39462]", children: h }),
            /* @__PURE__ */ R.jsx(y, { className: "h-8 w-8 text-[#294f5b]", strokeWidth: 1.3 })
          ] }),
          /* @__PURE__ */ R.jsx("h3", { className: "mt-10 font-serif text-3xl tracking-tight", children: v }),
          /* @__PURE__ */ R.jsx("p", { className: "mt-3 text-sm leading-[1.8] text-[#64757b]", children: b })
        ] }, h)) })
      ] }) }),
      /* @__PURE__ */ R.jsx("section", { id: "collection", className: "bg-[#edece6] px-5 py-20 md:px-10 md:py-28", children: /* @__PURE__ */ R.jsxs("div", { className: "mx-auto max-w-[1240px]", children: [
        /* @__PURE__ */ R.jsxs("div", { className: "mb-10 flex flex-wrap items-end justify-between gap-6", children: [
          /* @__PURE__ */ R.jsxs("div", { children: [
            /* @__PURE__ */ R.jsx("p", { className: "mb-3 text-[11px] font-extrabold uppercase tracking-[.22em] text-[#916d3b]", children: "The collection" }),
            /* @__PURE__ */ R.jsx("h2", { className: "font-serif text-[clamp(2.9rem,5vw,5rem)] leading-[1.08] tracking-[-.06em]", children: "Explore the possibilities." })
          ] }),
          /* @__PURE__ */ R.jsxs("a", { href: "/demo-stock/", className: "inline-flex items-center gap-2 border-b border-[#947a4d] pb-2 text-[11px] font-black uppercase tracking-widest text-[#173b48] no-underline", children: [
            "See demonstrator inventory ",
            /* @__PURE__ */ R.jsx(p3, { className: "h-4 w-4" })
          ] })
        ] }),
        /* @__PURE__ */ R.jsx("div", { className: "grid gap-4 md:grid-cols-3", children: w3.map((h) => /* @__PURE__ */ R.jsxs("article", { className: "group overflow-hidden rounded-lg border border-[#d1d9d6] bg-white", children: [
          /* @__PURE__ */ R.jsxs("div", { className: "relative flex h-64 flex-col justify-between overflow-hidden bg-gradient-to-br p-6 " + h.colors, children: [
            /* @__PURE__ */ R.jsx(pg, { reduce: i }),
            /* @__PURE__ */ R.jsxs("span", { className: "relative z-10 text-[10px] font-black uppercase tracking-[.23em] text-[#f1d8a9]", children: [
              "Concept ",
              h.num
            ] }),
            /* @__PURE__ */ R.jsx(Zf, { className: "relative z-10 mx-auto h-28 w-28 text-[#dfeaec]/70 drop-shadow-lg transition-transform duration-500 group-hover:scale-110", strokeWidth: 0.7, "aria-hidden": "true" }),
            /* @__PURE__ */ R.jsx("span", { className: "relative z-10 text-[10px] font-semibold uppercase tracking-widest text-slate-300", children: "Visual direction only" })
          ] }),
          /* @__PURE__ */ R.jsxs("div", { className: "p-7", children: [
            /* @__PURE__ */ R.jsx("h3", { className: "font-serif text-2xl tracking-tight", children: h.name }),
            /* @__PURE__ */ R.jsx("p", { className: "mt-2 text-sm text-[#6a787e]", children: "Inventory presentation concept" }),
            /* @__PURE__ */ R.jsxs("p", { className: "mt-5 inline-flex items-center gap-2 text-[10px] font-bold uppercase tracking-[.15em] text-[#987545]", children: [
              "No actual vehicle listing ",
              /* @__PURE__ */ R.jsx(Qf, { className: "h-4 w-4" })
            ] })
          ] })
        ] }, h.num)) })
      ] }) }),
      /* @__PURE__ */ R.jsx("section", { className: "bg-[#102832] px-5 py-20 text-white md:px-10 md:py-28", children: /* @__PURE__ */ R.jsxs("div", { className: "mx-auto flex max-w-[1240px] flex-col items-start justify-between gap-10 rounded-xl border border-[#d4ae75]/35 bg-[radial-gradient(ellipse_at_top_right,#214957_0%,#102832_50%,#091923_100%)] p-8 md:flex-row md:items-center md:p-14", children: [
        /* @__PURE__ */ R.jsxs("div", { children: [
          /* @__PURE__ */ R.jsx("p", { className: "mb-4 text-[10px] font-bold uppercase tracking-[.26em] text-[#d6b47d]", children: "A secure commercial foundation" }),
          /* @__PURE__ */ R.jsx("h2", { className: "max-w-[16ch] font-serif text-[clamp(2.7rem,4vw,4.5rem)] leading-[1.1] tracking-[-.05em]", children: "Designed to be extraordinary. Built to be responsible." }),
          /* @__PURE__ */ R.jsx("p", { className: "mt-5 max-w-[62ch] text-sm leading-[1.9] text-[#b9cbd2]", children: "Private bookings are verified in WordPress and MariaDB staging. Public booking, payments and customer enquiries remain disabled." })
        ] }),
        /* @__PURE__ */ R.jsx(bf, { primary: !0, palette: d, href: c.contact_path, children: c.contact_label })
      ] }) })
    ] }),
    /* @__PURE__ */ R.jsx("footer", { className: "border-t border-white/10 bg-[#07151f] px-5 py-12 text-[#b9c9ce] md:px-10", children: /* @__PURE__ */ R.jsxs("div", { className: "mx-auto flex max-w-[1240px] flex-col justify-between gap-6 md:flex-row", children: [
      /* @__PURE__ */ R.jsxs("div", { children: [
        /* @__PURE__ */ R.jsx("p", { className: "text-sm font-black uppercase tracking-[.2em] text-white", children: c.name }),
        /* @__PURE__ */ R.jsx("p", { className: "mt-2 max-w-[44ch] text-xs leading-7", children: "Fictional WordPress + React showroom made for internal Empire AI capability testing." })
      ] }),
      /* @__PURE__ */ R.jsxs("div", { className: "text-xs leading-7 md:text-right", children: [
        /* @__PURE__ */ R.jsx("p", { children: "No real vehicles, sales offers, reservations or customer data." }),
        /* @__PURE__ */ R.jsx("p", { children: "Client identity, privacy and commercial terms remain pending." })
      ] })
    ] }) })
  ] });
}
const bg = document.getElementById("empire-yard-react-root");
bg && dT.createRoot(bg).render(/* @__PURE__ */ R.jsx(V3, {}));
export {
  sT as R,
  oT as a,
  K as b,
  nT as g,
  R as j,
  Jf as r
};
