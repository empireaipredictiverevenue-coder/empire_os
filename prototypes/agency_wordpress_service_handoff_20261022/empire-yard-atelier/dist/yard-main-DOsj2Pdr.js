function eT(i) {
  return i && i.__esModule && Object.prototype.hasOwnProperty.call(i, "default") ? i.default : i;
}
var Pc = { exports: {} }, Kl = {};
var Xy;
function nT() {
  if (Xy) return Kl;
  Xy = 1;
  var i = /* @__PURE__ */ Symbol.for("react.transitional.element"), l = /* @__PURE__ */ Symbol.for("react.fragment");
  function r(o, c, h) {
    var d = null;
    if (h !== void 0 && (d = "" + h), c.key !== void 0 && (d = "" + c.key), "key" in c) {
      h = {};
      for (var p in c)
        p !== "key" && (h[p] = c[p]);
    } else h = c;
    return c = h.ref, {
      $$typeof: i,
      type: o,
      key: d,
      ref: c !== void 0 ? c : null,
      props: h
    };
  }
  return Kl.Fragment = l, Kl.jsx = r, Kl.jsxs = r, Kl;
}
var Zy;
function aT() {
  return Zy || (Zy = 1, Pc.exports = nT()), Pc.exports;
}
var w = aT(), Fc = { exports: {} }, ut = {};
var Qy;
function iT() {
  if (Qy) return ut;
  Qy = 1;
  var i = /* @__PURE__ */ Symbol.for("react.transitional.element"), l = /* @__PURE__ */ Symbol.for("react.portal"), r = /* @__PURE__ */ Symbol.for("react.fragment"), o = /* @__PURE__ */ Symbol.for("react.strict_mode"), c = /* @__PURE__ */ Symbol.for("react.profiler"), h = /* @__PURE__ */ Symbol.for("react.consumer"), d = /* @__PURE__ */ Symbol.for("react.context"), p = /* @__PURE__ */ Symbol.for("react.forward_ref"), v = /* @__PURE__ */ Symbol.for("react.suspense"), b = /* @__PURE__ */ Symbol.for("react.memo"), g = /* @__PURE__ */ Symbol.for("react.lazy"), y = /* @__PURE__ */ Symbol.for("react.activity"), T = /* @__PURE__ */ Symbol.for("react.view_transition"), V = Symbol.iterator;
  function R(E) {
    return E === null || typeof E != "object" ? null : (E = V && E[V] || E["@@iterator"], typeof E == "function" ? E : null);
  }
  var U = {
    isMounted: function() {
      return !1;
    },
    enqueueForceUpdate: function() {
    },
    enqueueReplaceState: function() {
    },
    enqueueSetState: function() {
    }
  }, j = Object.assign, H = {};
  function q(E, L, et) {
    this.props = E, this.context = L, this.refs = H, this.updater = et || U;
  }
  q.prototype.isReactComponent = {}, q.prototype.setState = function(E, L) {
    if (typeof E != "object" && typeof E != "function" && E != null)
      throw Error(
        "takes an object of state variables to update or a function which returns an object of state variables."
      );
    this.updater.enqueueSetState(this, E, L, "setState");
  }, q.prototype.forceUpdate = function(E) {
    this.updater.enqueueForceUpdate(this, E, "forceUpdate");
  };
  function X() {
  }
  X.prototype = q.prototype;
  function Q(E, L, et) {
    this.props = E, this.context = L, this.refs = H, this.updater = et || U;
  }
  var it = Q.prototype = new X();
  it.constructor = Q, j(it, q.prototype), it.isPureReactComponent = !0;
  var dt = Array.isArray;
  function J() {
  }
  var Z = { H: null, A: null, T: null, S: null }, Mt = Object.prototype.hasOwnProperty;
  function W(E, L, et) {
    var nt = et.ref;
    return {
      $$typeof: i,
      type: E,
      key: L,
      ref: nt !== void 0 ? nt : null,
      props: et
    };
  }
  function yt(E, L) {
    return W(E.type, L, E.props);
  }
  function ot(E) {
    return typeof E == "object" && E !== null && E.$$typeof === i;
  }
  function $t(E) {
    var L = { "=": "=0", ":": "=2" };
    return "$" + E.replace(/[=:]/g, function(et) {
      return L[et];
    });
  }
  var Zt = /\/+/g;
  function Ct(E, L) {
    return typeof E == "object" && E !== null && E.key != null ? $t("" + E.key) : L.toString(36);
  }
  function Y(E) {
    switch (E.status) {
      case "fulfilled":
        return E.value;
      case "rejected":
        throw E.reason;
      default:
        switch (typeof E.status == "string" ? E.then(J, J) : (E.status = "pending", E.then(
          function(L) {
            E.status === "pending" && (E.status = "fulfilled", E.value = L);
          },
          function(L) {
            E.status === "pending" && (E.status = "rejected", E.reason = L);
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
  function tt(E, L, et, nt, St) {
    var Tt = typeof E;
    (Tt === "undefined" || Tt === "boolean") && (E = null);
    var Et = !1;
    if (E === null) Et = !0;
    else
      switch (Tt) {
        case "bigint":
        case "string":
        case "number":
          Et = !0;
          break;
        case "object":
          switch (E.$$typeof) {
            case i:
            case l:
              Et = !0;
              break;
            case g:
              return Et = E._init, tt(
                Et(E._payload),
                L,
                et,
                nt,
                St
              );
          }
      }
    if (Et)
      return St = St(E), Et = nt === "" ? "." + Ct(E, 0) : nt, dt(St) ? (et = "", Et != null && (et = Et.replace(Zt, "$&/") + "/"), tt(St, L, et, "", function(An) {
        return An;
      })) : St != null && (ot(St) && (St = yt(
        St,
        et + (St.key == null || E && E.key === St.key ? "" : ("" + St.key).replace(
          Zt,
          "$&/"
        ) + "/") + Et
      )), L.push(St)), 1;
    Et = 0;
    var I = nt === "" ? "." : nt + ":";
    if (dt(E))
      for (var st = 0; st < E.length; st++)
        nt = E[st], Tt = I + Ct(nt, st), Et += tt(
          nt,
          L,
          et,
          Tt,
          St
        );
    else if (st = R(E), typeof st == "function")
      for (E = st.call(E), st = 0; !(nt = E.next()).done; )
        nt = nt.value, Tt = I + Ct(nt, st++), Et += tt(
          nt,
          L,
          et,
          Tt,
          St
        );
    else if (Tt === "object") {
      if (typeof E.then == "function")
        return tt(
          Y(E),
          L,
          et,
          nt,
          St
        );
      throw L = String(E), Error(
        "Objects are not valid as a React child (found: " + (L === "[object Object]" ? "object with keys {" + Object.keys(E).join(", ") + "}" : L) + "). If you meant to render a collection of children, use an array instead."
      );
    }
    return Et;
  }
  function B(E, L, et) {
    if (E == null) return E;
    var nt = [], St = 0;
    return tt(E, nt, "", "", function(Tt) {
      return L.call(et, Tt, St++);
    }), nt;
  }
  function at(E) {
    if (E._status === -1) {
      var L = E._result, et = L();
      et.then(
        function(nt) {
          (E._status === 0 || E._status === -1) && (E._status = 1, E._result = nt, et.status === void 0 && (et.status = "fulfilled", et.value = nt));
        },
        function(nt) {
          (E._status === 0 || E._status === -1) && (E._status = 2, E._result = nt, et.status === void 0 && (et.status = "rejected", et.reason = nt));
        }
      ), E._status === -1 && (E._status = 0, E._result = et);
    }
    if (E._status === 1) return E._result.default;
    throw E._result;
  }
  var ft = typeof reportError == "function" ? reportError : function(E) {
    if (typeof window == "object" && typeof window.ErrorEvent == "function") {
      var L = new window.ErrorEvent("error", {
        bubbles: !0,
        cancelable: !0,
        message: typeof E == "object" && E !== null && typeof E.message == "string" ? String(E.message) : String(E),
        error: E
      });
      if (!window.dispatchEvent(L)) return;
    } else if (typeof process == "object" && typeof process.emit == "function") {
      process.emit("uncaughtException", E);
      return;
    }
    console.error(E);
  };
  function Qt(E) {
    var L = Z.T, et = {};
    et.types = L !== null ? L.types : null, Z.T = et;
    try {
      var nt = E(), St = Z.S;
      St !== null && St(et, nt), typeof nt == "object" && nt !== null && typeof nt.then == "function" && nt.then(J, ft);
    } catch (Tt) {
      ft(Tt);
    } finally {
      L !== null && et.types !== null && (L.types = et.types), Z.T = L;
    }
  }
  function Fe(E) {
    var L = Z.T;
    if (L !== null) {
      var et = L.types;
      et === null ? L.types = [E] : et.indexOf(E) === -1 && et.push(E);
    } else Qt(Fe.bind(null, E));
  }
  var Ta = {
    map: B,
    forEach: function(E, L, et) {
      B(
        E,
        function() {
          L.apply(this, arguments);
        },
        et
      );
    },
    count: function(E) {
      var L = 0;
      return B(E, function() {
        L++;
      }), L;
    },
    toArray: function(E) {
      return B(E, function(L) {
        return L;
      }) || [];
    },
    only: function(E) {
      if (!ot(E))
        throw Error(
          "React.Children.only expected to receive a single React element child."
        );
      return E;
    }
  };
  return ut.Activity = y, ut.Children = Ta, ut.Component = q, ut.Fragment = r, ut.Profiler = c, ut.PureComponent = Q, ut.StrictMode = o, ut.Suspense = v, ut.ViewTransition = T, ut.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE = Z, ut.__COMPILER_RUNTIME = {
    __proto__: null,
    c: function(E) {
      return Z.H.useMemoCache(E);
    }
  }, ut.addTransitionType = Fe, ut.cache = function(E) {
    return function() {
      return E.apply(null, arguments);
    };
  }, ut.cacheSignal = function() {
    return null;
  }, ut.cloneElement = function(E, L, et) {
    if (E == null)
      throw Error(
        "The argument must be a React element, but you passed " + E + "."
      );
    var nt = j({}, E.props), St = E.key;
    if (L != null)
      for (Tt in L.key !== void 0 && (St = "" + L.key), L)
        !Mt.call(L, Tt) || Tt === "key" || Tt === "__self" || Tt === "__source" || Tt === "ref" && L.ref === void 0 || (nt[Tt] = L[Tt]);
    var Tt = arguments.length - 2;
    if (Tt === 1) nt.children = et;
    else if (1 < Tt) {
      for (var Et = Array(Tt), I = 0; I < Tt; I++)
        Et[I] = arguments[I + 2];
      nt.children = Et;
    }
    return W(E.type, St, nt);
  }, ut.createContext = function(E) {
    return E = {
      $$typeof: d,
      _currentValue: E,
      _currentValue2: E,
      _threadCount: 0,
      Provider: null,
      Consumer: null
    }, E.Provider = E, E.Consumer = {
      $$typeof: h,
      _context: E
    }, E;
  }, ut.createElement = function(E, L, et) {
    var nt, St = {}, Tt = null;
    if (L != null)
      for (nt in L.key !== void 0 && (Tt = "" + L.key), L)
        Mt.call(L, nt) && nt !== "key" && nt !== "__self" && nt !== "__source" && (St[nt] = L[nt]);
    var Et = arguments.length - 2;
    if (Et === 1) St.children = et;
    else if (1 < Et) {
      for (var I = Array(Et), st = 0; st < Et; st++)
        I[st] = arguments[st + 2];
      St.children = I;
    }
    if (E && E.defaultProps)
      for (nt in Et = E.defaultProps, Et)
        St[nt] === void 0 && (St[nt] = Et[nt]);
    return W(E, Tt, St);
  }, ut.createRef = function() {
    return { current: null };
  }, ut.forwardRef = function(E) {
    return { $$typeof: p, render: E };
  }, ut.isValidElement = ot, ut.lazy = function(E) {
    return {
      $$typeof: g,
      _payload: { _status: -1, _result: E },
      _init: at
    };
  }, ut.memo = function(E, L) {
    return {
      $$typeof: b,
      type: E,
      compare: L === void 0 ? null : L
    };
  }, ut.startTransition = Qt, ut.unstable_useCacheRefresh = function() {
    return Z.H.useCacheRefresh();
  }, ut.use = function(E) {
    return Z.H.use(E);
  }, ut.useActionState = function(E, L, et) {
    return Z.H.useActionState(E, L, et);
  }, ut.useCallback = function(E, L) {
    return Z.H.useCallback(E, L);
  }, ut.useContext = function(E) {
    return Z.H.useContext(E);
  }, ut.useDebugValue = function() {
  }, ut.useDeferredValue = function(E, L) {
    return Z.H.useDeferredValue(E, L);
  }, ut.useEffect = function(E, L) {
    return Z.H.useEffect(E, L);
  }, ut.useEffectEvent = function(E) {
    return Z.H.useEffectEvent(E);
  }, ut.useId = function() {
    return Z.H.useId();
  }, ut.useImperativeHandle = function(E, L, et) {
    return Z.H.useImperativeHandle(E, L, et);
  }, ut.useInsertionEffect = function(E, L) {
    return Z.H.useInsertionEffect(E, L);
  }, ut.useLayoutEffect = function(E, L) {
    return Z.H.useLayoutEffect(E, L);
  }, ut.useMemo = function(E, L) {
    return Z.H.useMemo(E, L);
  }, ut.useOptimistic = function(E, L) {
    return Z.H.useOptimistic(E, L);
  }, ut.useReducer = function(E, L, et) {
    return Z.H.useReducer(E, L, et);
  }, ut.useRef = function(E) {
    return Z.H.useRef(E);
  }, ut.useState = function(E) {
    return Z.H.useState(E);
  }, ut.useSyncExternalStore = function(E, L, et) {
    return Z.H.useSyncExternalStore(
      E,
      L,
      et
    );
  }, ut.useTransition = function() {
    return Z.H.useTransition();
  }, ut.version = "19.3.1", ut;
}
var Ky;
function Qf() {
  return Ky || (Ky = 1, Fc.exports = iT()), Fc.exports;
}
var K = Qf();
const lT = /* @__PURE__ */ eT(K);
var Wc = { exports: {} }, Jl = {}, Ic = { exports: {} }, $c = {};
var Jy;
function sT() {
  return Jy || (Jy = 1, (function(i) {
    function l(Y, tt) {
      var B = Y.length;
      Y.push(tt);
      t: for (; 0 < B; ) {
        var at = B - 1 >>> 1, ft = Y[at];
        if (0 < c(ft, tt))
          Y[at] = tt, Y[B] = ft, B = at;
        else break t;
      }
    }
    function r(Y) {
      return Y.length === 0 ? null : Y[0];
    }
    function o(Y) {
      if (Y.length === 0) return null;
      var tt = Y[0], B = Y.pop();
      if (B !== tt) {
        Y[0] = B;
        t: for (var at = 0, ft = Y.length, Qt = ft >>> 1; at < Qt; ) {
          var Fe = 2 * (at + 1) - 1, Ta = Y[Fe], E = Fe + 1, L = Y[E];
          if (0 > c(Ta, B))
            E < ft && 0 > c(L, Ta) ? (Y[at] = L, Y[E] = B, at = E) : (Y[at] = Ta, Y[Fe] = B, at = Fe);
          else if (E < ft && 0 > c(L, B))
            Y[at] = L, Y[E] = B, at = E;
          else break t;
        }
      }
      return tt;
    }
    function c(Y, tt) {
      var B = Y.sortIndex - tt.sortIndex;
      return B !== 0 ? B : Y.id - tt.id;
    }
    if (i.unstable_now = void 0, typeof performance == "object" && typeof performance.now == "function") {
      var h = performance;
      i.unstable_now = function() {
        return h.now();
      };
    } else {
      var d = Date, p = d.now();
      i.unstable_now = function() {
        return d.now() - p;
      };
    }
    var v = [], b = [], g = 1, y = null, T = 3, V = !1, R = !1, U = !1, j = !1, H = typeof setTimeout == "function" ? setTimeout : null, q = typeof clearTimeout == "function" ? clearTimeout : null, X = typeof setImmediate < "u" ? setImmediate : null;
    function Q(Y) {
      for (var tt = r(b); tt !== null; ) {
        if (tt.callback === null) o(b);
        else if (tt.startTime <= Y)
          o(b), tt.sortIndex = tt.expirationTime, l(v, tt);
        else break;
        tt = r(b);
      }
    }
    function it(Y) {
      if (U = !1, Q(Y), !R)
        if (r(v) !== null)
          R = !0, dt || (dt = !0, ot());
        else {
          var tt = r(b);
          tt !== null && Ct(it, tt.startTime - Y);
        }
    }
    var dt = !1, J = -1, Z = 5, Mt = -1;
    function W() {
      return j ? !0 : !(i.unstable_now() - Mt < Z);
    }
    function yt() {
      if (j = !1, dt) {
        var Y = i.unstable_now();
        Mt = Y;
        var tt = !0;
        try {
          t: {
            R = !1, U && (U = !1, q(J), J = -1), V = !0;
            var B = T;
            try {
              e: {
                for (Q(Y), y = r(v); y !== null && !(y.expirationTime > Y && W()); ) {
                  var at = y.callback;
                  if (typeof at == "function") {
                    y.callback = null, T = y.priorityLevel;
                    var ft = at(
                      y.expirationTime <= Y
                    );
                    if (Y = i.unstable_now(), typeof ft == "function") {
                      y.callback = ft, Q(Y), tt = !0;
                      break e;
                    }
                    y === r(v) && o(v), Q(Y);
                  } else o(v);
                  y = r(v);
                }
                if (y !== null) tt = !0;
                else {
                  var Qt = r(b);
                  Qt !== null && Ct(
                    it,
                    Qt.startTime - Y
                  ), tt = !1;
                }
              }
              break t;
            } finally {
              y = null, T = B, V = !1;
            }
            tt = void 0;
          }
        } finally {
          tt ? ot() : dt = !1;
        }
      }
    }
    var ot;
    if (typeof X == "function")
      ot = function() {
        X(yt);
      };
    else if (typeof MessageChannel < "u") {
      var $t = new MessageChannel(), Zt = $t.port2;
      $t.port1.onmessage = yt, ot = function() {
        Zt.postMessage(null);
      };
    } else
      ot = function() {
        H(yt, 0);
      };
    function Ct(Y, tt) {
      J = H(function() {
        Y(i.unstable_now());
      }, tt);
    }
    i.unstable_IdlePriority = 5, i.unstable_ImmediatePriority = 1, i.unstable_LowPriority = 4, i.unstable_NormalPriority = 3, i.unstable_Profiling = null, i.unstable_UserBlockingPriority = 2, i.unstable_cancelCallback = function(Y) {
      Y.callback = null;
    }, i.unstable_forceFrameRate = function(Y) {
      0 > Y || 125 < Y ? console.error(
        "forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported"
      ) : Z = 0 < Y ? Math.floor(1e3 / Y) : 5;
    }, i.unstable_getCurrentPriorityLevel = function() {
      return T;
    }, i.unstable_next = function(Y) {
      switch (T) {
        case 1:
        case 2:
        case 3:
          var tt = 3;
          break;
        default:
          tt = T;
      }
      var B = T;
      T = tt;
      try {
        return Y();
      } finally {
        T = B;
      }
    }, i.unstable_requestPaint = function() {
      j = !0;
    }, i.unstable_runWithPriority = function(Y, tt) {
      switch (Y) {
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
          break;
        default:
          Y = 3;
      }
      var B = T;
      T = Y;
      try {
        return tt();
      } finally {
        T = B;
      }
    }, i.unstable_scheduleCallback = function(Y, tt, B) {
      var at = i.unstable_now();
      switch (typeof B == "object" && B !== null ? (B = B.delay, B = typeof B == "number" && 0 < B ? at + B : at) : B = at, Y) {
        case 1:
          var ft = -1;
          break;
        case 2:
          ft = 250;
          break;
        case 5:
          ft = 1073741823;
          break;
        case 4:
          ft = 1e4;
          break;
        default:
          ft = 5e3;
      }
      return ft = B + ft, Y = {
        id: g++,
        callback: tt,
        priorityLevel: Y,
        startTime: B,
        expirationTime: ft,
        sortIndex: -1
      }, B > at ? (Y.sortIndex = B, l(b, Y), r(v) === null && Y === r(b) && (U ? (q(J), J = -1) : U = !0, Ct(it, B - at))) : (Y.sortIndex = ft, l(v, Y), R || V || (R = !0, dt || (dt = !0, ot()))), Y;
    }, i.unstable_shouldYield = W, i.unstable_wrapCallback = function(Y) {
      var tt = T;
      return function() {
        var B = T;
        T = tt;
        try {
          return Y.apply(this, arguments);
        } finally {
          T = B;
        }
      };
    };
  })($c)), $c;
}
var ky;
function uT() {
  return ky || (ky = 1, Ic.exports = sT()), Ic.exports;
}
var tf = { exports: {} }, fe = {};
var Py;
function oT() {
  if (Py) return fe;
  Py = 1;
  var i = Qf();
  function l(g) {
    var y = "https://react.dev/errors/" + g;
    if (1 < arguments.length) {
      y += "?args[]=" + encodeURIComponent(arguments[1]);
      for (var T = 2; T < arguments.length; T++)
        y += "&args[]=" + encodeURIComponent(arguments[T]);
    }
    return "Minified React error #" + g + "; visit " + y + " for the full message or use the non-minified dev environment for full errors and additional helpful warnings.";
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
  }, c = /* @__PURE__ */ Symbol.for("react.portal"), h = /* @__PURE__ */ Symbol.for("react.recoverable"), d = /* @__PURE__ */ Symbol.for("react.optimistic_key");
  function p(g, y, T) {
    var V = 3 < arguments.length && arguments[3] !== void 0 ? arguments[3] : null;
    return {
      $$typeof: c,
      key: V == null ? null : V === d ? d : "" + V,
      children: g,
      containerInfo: y,
      implementation: T
    };
  }
  var v = i.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;
  function b(g, y) {
    if (g === "font") return "";
    if (typeof y == "string")
      return y === "use-credentials" ? y : "";
  }
  return fe.__DOM_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE = o, fe.browser = function(g) {
    return { $$typeof: h, _reason: g };
  }, fe.createPortal = function(g, y) {
    var T = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null;
    if (!y || y.nodeType !== 1 && y.nodeType !== 9 && y.nodeType !== 11)
      throw Error(l(299));
    return p(g, y, null, T);
  }, fe.flushSync = function(g) {
    var y = v.T, T = o.p;
    try {
      if (v.T = null, o.p = 2, g) return g();
    } finally {
      v.T = y, o.p = T, o.d.f();
    }
  }, fe.preconnect = function(g, y) {
    typeof g == "string" && (y ? (y = y.crossOrigin, y = typeof y == "string" ? y === "use-credentials" ? y : "" : void 0) : y = null, o.d.C(g, y));
  }, fe.prefetchDNS = function(g) {
    typeof g == "string" && o.d.D(g);
  }, fe.preinit = function(g, y) {
    if (typeof g == "string" && y && typeof y.as == "string") {
      var T = y.as, V = b(T, y.crossOrigin), R = typeof y.integrity == "string" ? y.integrity : void 0, U = typeof y.fetchPriority == "string" ? y.fetchPriority : void 0;
      T === "style" ? o.d.S(
        g,
        typeof y.precedence == "string" ? y.precedence : void 0,
        {
          crossOrigin: V,
          integrity: R,
          fetchPriority: U
        }
      ) : T === "script" && o.d.X(g, {
        crossOrigin: V,
        integrity: R,
        fetchPriority: U,
        nonce: typeof y.nonce == "string" ? y.nonce : void 0
      });
    }
  }, fe.preinitModule = function(g, y) {
    if (typeof g == "string")
      if (typeof y == "object" && y !== null) {
        if (y.as == null || y.as === "script") {
          var T = b(
            y.as,
            y.crossOrigin
          );
          o.d.M(g, {
            crossOrigin: T,
            integrity: typeof y.integrity == "string" ? y.integrity : void 0,
            nonce: typeof y.nonce == "string" ? y.nonce : void 0,
            fetchPriority: typeof y.fetchPriority == "string" ? y.fetchPriority : void 0
          });
        }
      } else y == null && o.d.M(g);
  }, fe.preload = function(g, y) {
    if (typeof g == "string" && typeof y == "object" && y !== null && typeof y.as == "string") {
      var T = y.as, V = b(T, y.crossOrigin);
      o.d.L(g, T, {
        crossOrigin: V,
        integrity: typeof y.integrity == "string" ? y.integrity : void 0,
        nonce: typeof y.nonce == "string" ? y.nonce : void 0,
        type: typeof y.type == "string" ? y.type : void 0,
        fetchPriority: typeof y.fetchPriority == "string" ? y.fetchPriority : void 0,
        referrerPolicy: typeof y.referrerPolicy == "string" ? y.referrerPolicy : void 0,
        imageSrcSet: typeof y.imageSrcSet == "string" ? y.imageSrcSet : void 0,
        imageSizes: typeof y.imageSizes == "string" ? y.imageSizes : void 0,
        media: typeof y.media == "string" ? y.media : void 0
      });
    }
  }, fe.preloadModule = function(g, y) {
    if (typeof g == "string")
      if (y) {
        var T = b(y.as, y.crossOrigin);
        o.d.m(g, {
          as: typeof y.as == "string" && y.as !== "script" ? y.as : void 0,
          crossOrigin: T,
          integrity: typeof y.integrity == "string" ? y.integrity : void 0,
          nonce: typeof y.nonce == "string" ? y.nonce : void 0,
          fetchPriority: typeof y.fetchPriority == "string" ? y.fetchPriority : void 0
        });
      } else o.d.m(g);
  }, fe.requestFormReset = function(g) {
    o.d.r(g);
  }, fe.unstable_batchedUpdates = function(g, y) {
    return g(y);
  }, fe.useFormState = function(g, y, T) {
    return v.H.useFormState(g, y, T);
  }, fe.useFormStatus = function() {
    return v.H.useHostTransitionStatus();
  }, fe.version = "19.3.1", fe;
}
var Fy;
function rT() {
  if (Fy) return tf.exports;
  Fy = 1;
  function i() {
    if (!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" || typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function"))
      try {
        __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(i);
      } catch (l) {
        console.error(l);
      }
  }
  return i(), tf.exports = oT(), tf.exports;
}
var Wy;
function cT() {
  if (Wy) return Jl;
  Wy = 1;
  var i = uT(), l = Qf(), r = rT();
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
  function h(t) {
    for (var e = t, n = e; n && !n.alternate; )
      e = n, (e.flags & 4098) !== 0 && (t = e.return), n = e.return;
    for (; e.return; ) e = e.return;
    return e.tag === 3 ? t : null;
  }
  function d(t) {
    if (t.tag === 13) {
      var e = t.memoizedState;
      if (e === null && (t = t.alternate, t !== null && (e = t.memoizedState)), e !== null) return e.dehydrated;
    }
    return null;
  }
  function p(t) {
    if (t.tag === 31) {
      var e = t.memoizedState;
      if (e === null && (t = t.alternate, t !== null && (e = t.memoizedState)), e !== null) return e.dehydrated;
    }
    return null;
  }
  function v(t) {
    if (h(t) !== t)
      throw Error(o(188));
  }
  function b(t) {
    var e = t.alternate;
    if (!e) {
      if (e = h(t), e === null) throw Error(o(188));
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
  function y(t, e, n, a, s, u) {
    for (; t !== null; ) {
      if ((t.tag === 5 || t.tag === 27 || t.tag === 6) && n(t, a, s, u) || (t.tag !== 22 || t.memoizedState === null) && (e || t.tag !== 5 && t.tag !== 27) && y(
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
  function R(t) {
    var e = [null, null], n = T(t);
    return n === null || U(
      e,
      t,
      n.child,
      { foundSelf: !1 }
    ), e;
  }
  function U(t, e, n, a) {
    for (; n !== null; ) {
      if (n === e) a.foundSelf = !0;
      else if (n.tag === 5 || n.tag === 27 || n.tag === 6) {
        if (a.foundSelf) return t[1] = n, !0;
        t[0] = n;
      } else if ((n.tag !== 22 || n.memoizedState === null) && U(
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
  var H = null, q = null;
  function X(t, e, n) {
    return t === n ? !0 : t === e ? (H = t, !0) : !1;
  }
  function Q(t, e, n) {
    return t === n ? (q = t, !1) : t === e ? (q !== null && (H = t), !0) : !1;
  }
  function it(t) {
    if (t === null) return null;
    do
      t = t === null ? null : t.return;
    while (t && t.tag !== 5 && t.tag !== 27 && t.tag !== 3);
    return t || null;
  }
  function dt(t, e, n) {
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
  var J = Object.assign, Z = /* @__PURE__ */ Symbol.for("react.element"), Mt = /* @__PURE__ */ Symbol.for("react.transitional.element"), W = /* @__PURE__ */ Symbol.for("react.portal"), yt = /* @__PURE__ */ Symbol.for("react.fragment"), ot = /* @__PURE__ */ Symbol.for("react.strict_mode"), $t = /* @__PURE__ */ Symbol.for("react.profiler"), Zt = /* @__PURE__ */ Symbol.for("react.consumer"), Ct = /* @__PURE__ */ Symbol.for("react.context"), Y = /* @__PURE__ */ Symbol.for("react.forward_ref"), tt = /* @__PURE__ */ Symbol.for("react.suspense"), B = /* @__PURE__ */ Symbol.for("react.suspense_list"), at = /* @__PURE__ */ Symbol.for("react.memo"), ft = /* @__PURE__ */ Symbol.for("react.lazy"), Qt = /* @__PURE__ */ Symbol.for("react.activity"), Fe = /* @__PURE__ */ Symbol.for("react.legacy_hidden"), Ta = /* @__PURE__ */ Symbol.for("react.memo_cache_sentinel"), E = /* @__PURE__ */ Symbol.for("react.view_transition"), L = /* @__PURE__ */ Symbol.for("react.recoverable"), et = Symbol.iterator;
  function nt(t) {
    return t === null || typeof t != "object" ? null : (t = et && t[et] || t["@@iterator"], typeof t == "function" ? t : null);
  }
  var St = /* @__PURE__ */ Symbol.for("react.client.reference");
  function Tt(t) {
    if (t == null) return null;
    if (typeof t == "function")
      return t.$$typeof === St ? null : t.displayName || t.name || null;
    if (typeof t == "string") return t;
    switch (t) {
      case yt:
        return "Fragment";
      case $t:
        return "Profiler";
      case ot:
        return "StrictMode";
      case tt:
        return "Suspense";
      case B:
        return "SuspenseList";
      case Qt:
        return "Activity";
      case E:
        return "ViewTransition";
    }
    if (typeof t == "object")
      switch (t.$$typeof) {
        case W:
          return "Portal";
        case Ct:
          return t.displayName || "Context";
        case Zt:
          return (t._context.displayName || "Context") + ".Consumer";
        case Y:
          var e = t.render;
          return t = t.displayName, t || (t = e.displayName || e.name || "", t = t !== "" ? "ForwardRef(" + t + ")" : "ForwardRef"), t;
        case at:
          return e = t.displayName || null, e !== null ? e : Tt(t.type) || "Memo";
        case ft:
          e = t._payload, t = t._init;
          try {
            return Tt(t(e));
          } catch {
          }
      }
    return null;
  }
  var Et = Array.isArray, I = l.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, st = r.__DOM_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, An = {
    pending: !1,
    data: null,
    method: null,
    action: null
  }, mo = [], Ia = -1;
  function un(t) {
    return { current: t };
  }
  function ie(t) {
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
        t = (t = e.documentElement) && (t = t.namespaceURI) ? Ip(t) : 0;
        break;
      default:
        if (t = e.tagName, e = e.namespaceURI)
          e = Ip(e), t = $p(e, t);
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
    ie(on), jt(on, t);
  }
  function $a() {
    ie(on), ie(Ii), ie(qn);
  }
  function po(t) {
    var e = t.memoizedState;
    e !== null && (Yi._currentValue = e.memoizedState, jt(os, t)), e = on.current;
    var n = $p(e, t.type);
    e !== n && (jt(Ii, t), jt(on, n));
  }
  function cs(t) {
    Ii.current === t && (ie(on), ie(Ii)), os.current === t && (ie(os), Yi._currentValue = An);
  }
  var yo, bd;
  function Gn(t) {
    if (yo === void 0)
      try {
        throw Error();
      } catch (n) {
        var e = n.stack.trim().match(/\n( *(at )?)/);
        yo = e && e[1] || "", bd = -1 < n.stack.indexOf(`
    at`) ? " (<anonymous>)" : -1 < n.stack.indexOf("@") ? "@unknown:0:0" : "";
      }
    return `
` + yo + t + bd;
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
              var _ = function() {
                throw Error();
              };
              if (Object.defineProperty(_.prototype, "props", {
                set: function() {
                  throw Error();
                }
              }), typeof Reflect == "object" && Reflect.construct) {
                try {
                  Reflect.construct(_, []);
                } catch (G) {
                  var A = G;
                }
                Reflect.construct(t, [], _);
              } else {
                try {
                  _.call();
                } catch (G) {
                  A = G;
                }
                _ = !1;
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
                  }), _ = !0, new t();
                } finally {
                  _ && (O !== void 0 ? Object.defineProperty(t.prototype, "props", O) : delete t.prototype.props);
                }
              }
            } else {
              try {
                throw Error();
              } catch (G) {
                A = G;
              }
              (_ = t()) && typeof _.catch == "function" && _.catch(function() {
              });
            }
          } catch (G) {
            if (G && A && typeof G.stack == "string")
              return [G.stack, A.stack];
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
`), C = m.split(`
`);
        for (s = a = 0; a < S.length && !S[a].includes("DetermineComponentFrameRoot"); )
          a++;
        for (; s < C.length && !C[s].includes(
          "DetermineComponentFrameRoot"
        ); )
          s++;
        if (a === S.length || s === C.length)
          for (a = S.length - 1, s = C.length - 1; 1 <= a && 0 <= s && S[a] !== C[s]; )
            s--;
        for (; 1 <= a && 0 <= s; a--, s--)
          if (S[a] !== C[s]) {
            if (a !== 1 || s !== 1)
              do
                if (a--, s--, 0 > s || S[a] !== C[s]) {
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
  function l1(t, e) {
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
  function Sd(t) {
    try {
      var e = "", n = null;
      do
        e += l1(t, n), n = t, t = t.return;
      while (t);
      return e;
    } catch (a) {
      return `
Error generating stack: ` + a.message + `
` + a.stack;
    }
  }
  var bo = Object.prototype.hasOwnProperty, So = i.unstable_scheduleCallback, To = i.unstable_cancelCallback, s1 = i.unstable_shouldYield, u1 = i.unstable_requestPaint, De = i.unstable_now, o1 = i.unstable_getCurrentPriorityLevel, Td = i.unstable_ImmediatePriority, xd = i.unstable_UserBlockingPriority, fs = i.unstable_NormalPriority, r1 = i.unstable_LowPriority, Ed = i.unstable_IdlePriority, c1 = i.log, f1 = i.unstable_setDisableYieldValue, $i = null, Oe = null;
  function Xn(t) {
    if (typeof c1 == "function" && f1(t), Oe && typeof Oe.setStrictMode == "function")
      try {
        Oe.setStrictMode($i, t);
      } catch {
      }
  }
  var Ne = Math.clz32 ? Math.clz32 : m1, d1 = Math.log, h1 = Math.LN2;
  function m1(t) {
    return t >>>= 0, t === 0 ? 32 : 31 - (d1(t) / h1 | 0) | 0;
  }
  var ds = 256, hs = 262144, ms = 4194304;
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
  function ps(t, e, n) {
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
  function Ad(t, e) {
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
  function Md() {
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
  function y1(t, e, n, a, s, u) {
    var f = t.pendingLanes;
    t.pendingLanes = n, t.suspendedLanes = 0, t.pingedLanes = 0, t.warmLanes = 0, t.expiredLanes &= n, t.entangledLanes &= n, t.errorRecoveryDisabledLanes &= n, t.shellSuspendCounter = 0;
    var m = t.entanglements, S = t.expirationTimes, C = t.hiddenUpdates;
    for (n = f & ~n; 0 < n; ) {
      var N = 31 - Ne(n), _ = 1 << N;
      m[N] = 0, S[N] = -1;
      var A = C[N];
      if (A !== null)
        for (C[N] = null, N = 0; N < A.length; N++) {
          var O = A[N];
          O !== null && (O.lane &= -536870913);
        }
      n &= ~_;
    }
    a !== 0 && Cd(t, a, 0), u !== 0 && s === 0 && t.tag !== 0 && (t.suspendedLanes |= u & ~(f & ~e));
  }
  function Cd(t, e, n) {
    t.pendingLanes |= e, t.suspendedLanes &= ~e;
    var a = 31 - Ne(e);
    t.entangledLanes |= e, t.entanglements[a] = t.entanglements[a] | 1073741824 | n & 261930;
  }
  function Dd(t, e) {
    var n = t.entangledLanes |= e;
    for (t = t.entanglements; n; ) {
      var a = 31 - Ne(n), s = 1 << a;
      s & e | t[a] & e && (t[a] |= e), n &= ~s;
    }
  }
  function Od(t, e) {
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
  function Nd() {
    var t = st.p;
    return t !== 0 ? t : (t = window.event, t === void 0 ? 32 : Uy(t.type));
  }
  function wd(t, e) {
    var n = st.p;
    try {
      return st.p = t, e();
    } finally {
      st.p = n;
    }
  }
  var Mn = Math.random().toString(36).slice(2), le = "__reactFiber$" + Mn, Te = "__reactProps$" + Mn, ti = "__reactContainer$" + Mn, Rd = "__reactEvents$" + Mn, g1 = "__reactListeners$" + Mn, v1 = "__reactHandles$" + Mn, zd = "__reactResources$" + Mn, nl = "__reactMarker$" + Mn, ys = "__reactLoad$" + Mn;
  function gs(t) {
    delete t[le], delete t[Te], delete t[g1], delete t[v1];
  }
  function Ea(t) {
    var e;
    if (e = t[le]) return e;
    for (var n = t.parentNode; n; ) {
      if (e = n[ti] || n[le]) {
        if (n = e.alternate, e.child !== null || n !== null && n.child !== null)
          for (t = yy(t); t !== null; ) {
            if (n = t[le]) return n;
            t = yy(t);
          }
        return e;
      }
      t = n, n = t.parentNode;
    }
    return null;
  }
  function ei(t) {
    if (t = t[le] || t[ti]) {
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
    var e = t[zd];
    return e || (e = t[zd] = { hoistableStyles: /* @__PURE__ */ new Map(), hoistableScripts: /* @__PURE__ */ new Map() }), e;
  }
  function te(t) {
    t[nl] = !0;
  }
  function _d(t) {
    t[ys] = void 0;
  }
  var Vd = /* @__PURE__ */ new Set(), jd = {};
  function Aa(t, e) {
    ai(t, e), ai(t + "Capture", e);
  }
  function ai(t, e) {
    for (jd[t] = e, t = 0; t < e.length; t++)
      Vd.add(e[t]);
  }
  var b1 = RegExp(
    "^[:A-Z_a-z\\u00C0-\\u00D6\\u00D8-\\u00F6\\u00F8-\\u02FF\\u0370-\\u037D\\u037F-\\u1FFF\\u200C-\\u200D\\u2070-\\u218F\\u2C00-\\u2FEF\\u3001-\\uD7FF\\uF900-\\uFDCF\\uFDF0-\\uFFFD][:A-Z_a-z\\u00C0-\\u00D6\\u00D8-\\u00F6\\u00F8-\\u02FF\\u0370-\\u037D\\u037F-\\u1FFF\\u200C-\\u200D\\u2070-\\u218F\\u2C00-\\u2FEF\\u3001-\\uD7FF\\uF900-\\uFDCF\\uFDF0-\\uFFFD\\-.0-9\\u00B7\\u0300-\\u036F\\u203F-\\u2040]*$"
  ), Ud = {}, Bd = {};
  function S1(t) {
    return bo.call(Bd, t) ? !0 : bo.call(Ud, t) ? !1 : b1.test(t) ? Bd[t] = !0 : (Ud[t] = !0, !1);
  }
  var xt = !1;
  function Ld() {
    var t = xt;
    return xt = !1, t;
  }
  function vs(t, e, n) {
    if (S1(e))
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
  function Cn(t, e, n, a) {
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
  function we(t) {
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
  function Hd(t) {
    var e = t.type;
    return (t = t.nodeName) && t.toLowerCase() === "input" && (e === "checkbox" || e === "radio");
  }
  function T1(t, e, n) {
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
      var e = Hd(t) ? "checked" : "value";
      t._valueTracker = T1(
        t,
        e,
        "" + t[e]
      );
    }
  }
  function Yd(t) {
    if (!t) return !1;
    var e = t._valueTracker;
    if (!e) return !0;
    var n = e.getValue(), a = "";
    return t && (a = Hd(t) ? t.checked ? "true" : "false" : t.value), t = a, t !== n ? (e.setValue(t), !0) : !1;
  }
  var x1 = /[\n"\\]/g;
  function He(t) {
    return t.replace(
      x1,
      function(e) {
        return "\\" + e.charCodeAt(0).toString(16) + " ";
      }
    );
  }
  function Co(t, e, n, a, s, u, f, m) {
    t.name = "", f != null && typeof f != "function" && typeof f != "symbol" && typeof f != "boolean" ? t.type = f : t.removeAttribute("type"), e != null ? f === "number" ? (e === 0 && t.value === "" || t.value != e) && (t.value = "" + we(e)) : t.value !== "" + we(e) && (t.value = "" + we(e)) : f !== "submit" && f !== "reset" || t.removeAttribute("value"), e != null ? f === "number" && t.value == e ? Do(t, we(t.value)) : Do(t, we(e)) : n != null ? Do(t, we(n)) : a != null && t.removeAttribute("value"), s == null && u != null && (t.defaultChecked = !!u), s != null && (t.checked = s && typeof s != "function" && typeof s != "symbol"), m != null && typeof m != "function" && typeof m != "symbol" && typeof m != "boolean" ? t.name = "" + we(m) : t.removeAttribute("name");
  }
  function qd(t, e, n, a, s, u, f, m) {
    if (u != null && typeof u != "function" && typeof u != "symbol" && typeof u != "boolean" && (t.type = u), e != null || n != null) {
      if (!(u !== "submit" && u !== "reset" || e != null)) {
        Mo(t);
        return;
      }
      n = n != null ? "" + we(n) : "", e = e != null ? "" + we(e) : n, m || e === t.value || (t.value = e), t.defaultValue = e;
    }
    a = a ?? s, a = typeof a != "function" && typeof a != "symbol" && !!a, t.checked = m ? t.checked : !!a, t.defaultChecked = !!a, f != null && typeof f != "function" && typeof f != "symbol" && typeof f != "boolean" && (t.name = f), Mo(t);
  }
  function Do(t, e) {
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
      for (n = "" + we(n), e = null, s = 0; s < t.length; s++) {
        if (t[s].value === n) {
          t[s].selected = !0, a && (t[s].defaultSelected = !0);
          return;
        }
        e !== null || t[s].disabled || (e = t[s]);
      }
      e !== null && (e.selected = !0);
    }
  }
  function Gd(t, e, n) {
    if (e != null && (e = "" + we(e), e !== t.value && (t.value = e), n == null)) {
      t.defaultValue !== e && (t.defaultValue = e);
      return;
    }
    t.defaultValue = n != null ? "" + we(n) : "";
  }
  function Xd(t, e, n, a) {
    if (e == null) {
      if (a != null) {
        if (n != null) throw Error(o(92));
        if (Et(a)) {
          if (1 < a.length) throw Error(o(93));
          a = a[0];
        }
        n = a;
      }
      n == null && (n = ""), e = n;
    }
    n = we(e), t.defaultValue = n, a = t.textContent, a === n && a !== "" && a !== null && (t.value = a), Mo(t);
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
  var E1 = new Set(
    "animationIterationCount aspectRatio borderImageOutset borderImageSlice borderImageWidth boxFlex boxFlexGroup boxOrdinalGroup columnCount columns flex flexGrow flexPositive flexShrink flexNegative flexOrder gridArea gridRow gridRowEnd gridRowSpan gridRowStart gridColumn gridColumnEnd gridColumnSpan gridColumnStart fontWeight lineClamp lineHeight opacity order orphans scale tabSize widows zIndex zoom fillOpacity floodOpacity stopOpacity strokeDasharray strokeDashoffset strokeMiterlimit strokeOpacity strokeWidth MozAnimationIterationCount MozBoxFlex MozBoxFlexGroup MozLineClamp msAnimationIterationCount msFlex msZoom msFlexGrow msFlexNegative msFlexOrder msFlexPositive msFlexShrink msGridColumn msGridColumnSpan msGridRow msGridRowSpan WebkitAnimationIterationCount WebkitBoxFlex WebKitBoxFlexGroup WebkitBoxOrdinalGroup WebkitColumnCount WebkitColumns WebkitFlex WebkitFlexGrow WebkitFlexPositive WebkitFlexShrink WebkitLineClamp".split(
      " "
    )
  );
  function Zd(t, e, n) {
    var a = e.indexOf("--") === 0;
    n == null || typeof n == "boolean" || n === "" ? a ? t.setProperty(e, "") : e === "float" ? t.cssFloat = "" : t[e] = "" : a ? t.setProperty(e, n) : typeof n != "number" || n === 0 || E1.has(e) ? e === "float" ? t.cssFloat = n : t[e] = ("" + n).trim() : t[e] = n + "px";
  }
  function Qd(t, e, n) {
    if (e != null && typeof e != "object")
      throw Error(o(62));
    if (t = t.style, n != null) {
      for (var a in n)
        !n.hasOwnProperty(a) || e != null && e.hasOwnProperty(a) || (a.indexOf("--") === 0 ? t.setProperty(a, "") : a === "float" ? t.cssFloat = "" : t[a] = "", xt = !0);
      for (var s in e)
        a = e[s], e.hasOwnProperty(s) && n[s] !== a && (Zd(t, s, a), xt = !0);
    } else
      for (var u in e)
        e.hasOwnProperty(u) && Zd(t, u, e[u]);
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
  var A1 = /* @__PURE__ */ new Map([
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
  ]), M1 = /^[\u0000-\u001F ]*j[\r\n\t]*a[\r\n\t]*v[\r\n\t]*a[\r\n\t]*s[\r\n\t]*c[\r\n\t]*r[\r\n\t]*i[\r\n\t]*p[\r\n\t]*t[\r\n\t]*:/i;
  function Ss(t) {
    return M1.test("" + t) ? "javascript:throw new Error('React has blocked a javascript: URL as a security precaution.')" : t;
  }
  function rn() {
  }
  var No = null;
  function wo(t) {
    return t = t.target || t.srcElement || window, t.correspondingUseElement && (t = t.correspondingUseElement), t.nodeType === 3 ? t.parentNode : t;
  }
  var si = null, ui = null;
  function Kd(t) {
    var e = ei(t);
    if (e && (t = e.stateNode)) {
      var n = t[Te] || null;
      t: switch (t = e.stateNode, e.type) {
        case "input":
          if (Co(
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
              'input[name="' + He(
                "" + e
              ) + '"][type="radio"]'
            ), e = 0; e < n.length; e++) {
              var a = n[e];
              if (a !== t && a.form === t.form) {
                var s = a[Te] || null;
                if (!s) throw Error(o(90));
                Co(
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
              a = n[e], a.form === t.form && Yd(a);
          }
          break t;
        case "textarea":
          Gd(t, n.value, n.defaultValue);
          break t;
        case "select":
          e = n.value, e != null && ii(t, !!n.multiple, e, !1);
      }
    }
  }
  var Ro = !1;
  function Jd(t, e, n) {
    if (Ro) return t(e, n);
    Ro = !0;
    try {
      var a = t(e);
      return a;
    } finally {
      if (Ro = !1, (si !== null || ui !== null) && (Su(), si && (e = si, t = ui, ui = si = null, Kd(e), t)))
        for (e = 0; e < t.length; e++) Kd(t[e]);
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
  var Dn = !(typeof window > "u" || typeof window.document > "u" || typeof window.document.createElement > "u"), zo = !1;
  if (Dn)
    try {
      var ll = {};
      Object.defineProperty(ll, "passive", {
        get: function() {
          zo = !0;
        }
      }), window.addEventListener("test", ll, ll), window.removeEventListener("test", ll, ll);
    } catch {
      zo = !1;
    }
  var Zn = null, _o = null, Ts = null;
  function kd() {
    if (Ts) return Ts;
    var t, e = _o, n = e.length, a, s = "value" in Zn ? Zn.value : Zn.textContent, u = s.length;
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
  function Pd() {
    return !1;
  }
  function pe(t) {
    function e(n, a, s, u, f) {
      this._reactName = n, this._targetInst = s, this.type = a, this.nativeEvent = u, this.target = f, this.currentTarget = null;
      for (var m in t)
        t.hasOwnProperty(m) && (n = t[m], this[m] = n ? n(u) : u[m]);
      return this.isDefaultPrevented = (u.defaultPrevented != null ? u.defaultPrevented : u.returnValue === !1) ? Es : Pd, this.isPropagationStopped = Pd, this;
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
  var Qn = {
    eventPhase: 0,
    bubbles: 0,
    cancelable: 0,
    timeStamp: function(t) {
      return t.timeStamp || Date.now();
    },
    defaultPrevented: 0,
    isTrusted: 0
  }, As = pe(Qn), sl = J({}, Qn, { view: 0, detail: 0 }), C1 = pe(sl), Vo, jo, ul, Ms = J({}, sl, {
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
  }), Fd = pe(Ms), D1 = J({}, Ms, { dataTransfer: 0 }), O1 = pe(D1), N1 = J({}, sl, { relatedTarget: 0 }), Uo = pe(N1), w1 = J({}, Qn, {
    animationName: 0,
    elapsedTime: 0,
    pseudoElement: 0
  }), R1 = pe(w1), z1 = J({}, Qn, {
    clipboardData: function(t) {
      return "clipboardData" in t ? t.clipboardData : window.clipboardData;
    }
  }), _1 = pe(z1), V1 = J({}, Qn, { data: 0 }), Wd = pe(V1), j1 = {
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
  }, U1 = {
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
  }, B1 = {
    Alt: "altKey",
    Control: "ctrlKey",
    Meta: "metaKey",
    Shift: "shiftKey"
  };
  function L1(t) {
    var e = this.nativeEvent;
    return e.getModifierState ? e.getModifierState(t) : (t = B1[t]) ? !!e[t] : !1;
  }
  function Bo() {
    return L1;
  }
  var H1 = J({}, sl, {
    key: function(t) {
      if (t.key) {
        var e = j1[t.key] || t.key;
        if (e !== "Unidentified") return e;
      }
      return t.type === "keypress" ? (t = xs(t), t === 13 ? "Enter" : String.fromCharCode(t)) : t.type === "keydown" || t.type === "keyup" ? U1[t.keyCode] || "Unidentified" : "";
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
  }), Y1 = pe(H1), q1 = J({}, Ms, {
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
  }), Id = pe(q1), G1 = J({}, Qn, { submitter: 0 }), X1 = pe(G1), Z1 = J({}, sl, {
    touches: 0,
    targetTouches: 0,
    changedTouches: 0,
    altKey: 0,
    metaKey: 0,
    ctrlKey: 0,
    shiftKey: 0,
    getModifierState: Bo
  }), Q1 = pe(Z1), K1 = J({}, Qn, {
    propertyName: 0,
    elapsedTime: 0,
    pseudoElement: 0
  }), J1 = pe(K1), k1 = J({}, Ms, {
    deltaX: function(t) {
      return "deltaX" in t ? t.deltaX : "wheelDeltaX" in t ? -t.wheelDeltaX : 0;
    },
    deltaY: function(t) {
      return "deltaY" in t ? t.deltaY : "wheelDeltaY" in t ? -t.wheelDeltaY : "wheelDelta" in t ? -t.wheelDelta : 0;
    },
    deltaZ: 0,
    deltaMode: 0
  }), P1 = pe(k1), F1 = J({}, Qn, {
    newState: 0,
    oldState: 0,
    source: 0
  }), W1 = pe(F1), I1 = [9, 13, 27, 32], Lo = Dn && "CompositionEvent" in window, ol = null;
  Dn && "documentMode" in document && (ol = document.documentMode);
  var $1 = Dn && "TextEvent" in window && !ol, $d = Dn && (!Lo || ol && 8 < ol && 11 >= ol), th = " ", eh = !1;
  function nh(t, e) {
    switch (t) {
      case "keyup":
        return I1.indexOf(e.keyCode) !== -1;
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
  function ah(t) {
    return t = t.detail, typeof t == "object" && "data" in t ? t.data : null;
  }
  var oi = !1;
  function tb(t, e) {
    switch (t) {
      case "compositionend":
        return ah(e);
      case "keypress":
        return e.which !== 32 ? null : (eh = !0, th);
      case "textInput":
        return t = e.data, t === th && eh ? null : t;
      default:
        return null;
    }
  }
  function eb(t, e) {
    if (oi)
      return t === "compositionend" || !Lo && nh(t, e) ? (t = kd(), Ts = _o = Zn = null, oi = !1, t) : null;
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
        return $d && e.locale !== "ko" ? null : e.data;
      default:
        return null;
    }
  }
  var nb = {
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
  function ih(t) {
    var e = t && t.nodeName && t.nodeName.toLowerCase();
    return e === "input" ? !!nb[t.type] : e === "textarea";
  }
  function lh(t, e, n, a) {
    si ? ui ? ui.push(a) : ui = [a] : si = a, e = Cu(e, "onChange"), 0 < e.length && (n = new As(
      "onChange",
      "change",
      null,
      n,
      a
    ), t.push({ event: n, listeners: e }));
  }
  var rl = null, cl = null;
  function ab(t) {
    Kp(t, 0);
  }
  function Cs(t) {
    var e = al(t);
    if (Yd(e)) return t;
  }
  function sh(t, e) {
    if (t === "change") return e;
  }
  var uh = !1;
  if (Dn) {
    var Ho;
    if (Dn) {
      var Yo = "oninput" in document;
      if (!Yo) {
        var oh = document.createElement("div");
        oh.setAttribute("oninput", "return;"), Yo = typeof oh.oninput == "function";
      }
      Ho = Yo;
    } else Ho = !1;
    uh = Ho && (!document.documentMode || 9 < document.documentMode);
  }
  function rh() {
    rl && (rl.detachEvent("onpropertychange", ch), cl = rl = null);
  }
  function ch(t) {
    if (t.propertyName === "value" && Cs(cl)) {
      var e = [];
      lh(
        e,
        cl,
        t,
        wo(t)
      ), Jd(ab, e);
    }
  }
  function ib(t, e, n) {
    t === "focusin" ? (rh(), rl = e, cl = n, rl.attachEvent("onpropertychange", ch)) : t === "focusout" && rh();
  }
  function lb(t) {
    if (t === "selectionchange" || t === "keyup" || t === "keydown")
      return Cs(cl);
  }
  function sb(t, e) {
    if (t === "click") return Cs(e);
  }
  function ub(t, e) {
    if (t === "input" || t === "change")
      return Cs(e);
  }
  function ob(t, e) {
    return t === e && (t !== 0 || 1 / t === 1 / e) || t !== t && e !== e;
  }
  var Re = typeof Object.is == "function" ? Object.is : ob;
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
  function fh(t) {
    for (; t && t.firstChild; ) t = t.firstChild;
    return t;
  }
  function dh(t, e) {
    var n = fh(t);
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
      n = fh(n);
    }
  }
  function hh(t, e) {
    return t && e ? t === e ? !0 : t && t.nodeType === 3 ? !1 : e && e.nodeType === 3 ? hh(t, e.parentNode) : "contains" in t ? t.contains(e) : t.compareDocumentPosition ? !!(t.compareDocumentPosition(e) & 16) : !1 : !1;
  }
  function mh(t) {
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
  var rb = Dn && "documentMode" in document && 11 >= document.documentMode, ri = null, Xo = null, dl = null, Zo = !1;
  function ph(t, e, n) {
    var a = n.window === n ? n.document : n.nodeType === 9 ? n : n.ownerDocument;
    Zo || ri == null || ri !== qo(a) || (a = ri, "selectionStart" in a && Go(a) ? a = { start: a.selectionStart, end: a.selectionEnd } : (a = (a.ownerDocument && a.ownerDocument.defaultView || window).getSelection(), a = {
      anchorNode: a.anchorNode,
      anchorOffset: a.anchorOffset,
      focusNode: a.focusNode,
      focusOffset: a.focusOffset
    }), dl && fl(dl, a) || (dl = a, a = Cu(Xo, "onSelect"), 0 < a.length && (e = new As(
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
  }, Qo = {}, yh = {};
  Dn && (yh = document.createElement("div").style, "AnimationEvent" in window || (delete ci.animationend.animation, delete ci.animationiteration.animation, delete ci.animationstart.animation), "TransitionEvent" in window || delete ci.transitionend.transition);
  function Ca(t) {
    if (Qo[t]) return Qo[t];
    if (!ci[t]) return t;
    var e = ci[t], n;
    for (n in e)
      if (e.hasOwnProperty(n) && n in yh)
        return Qo[t] = e[n];
    return t;
  }
  var gh = Ca("animationend"), vh = Ca("animationiteration"), bh = Ca("animationstart"), cb = Ca("transitionrun"), fb = Ca("transitionstart"), db = Ca("transitioncancel"), Sh = Ca("transitionend"), Th = /* @__PURE__ */ new Map(), Ko = "abort auxClick beforeToggle cancel canPlay canPlayThrough click close contextMenu copy cut drag dragEnd dragEnter dragExit dragLeave dragOver dragStart drop durationChange emptied encrypted ended error fullscreenChange fullscreenError gotPointerCapture input invalid keyDown keyPress keyUp load loadedData loadedMetadata loadStart lostPointerCapture mouseDown mouseMove mouseOut mouseOver mouseUp paste pause play playing pointerCancel pointerDown pointerMove pointerOut pointerOver pointerUp progress rateChange reset resize seeked seeking stalled submit suspend timeUpdate touchCancel touchEnd touchStart volumeChange scroll toggle touchMove waiting wheel".split(
    " "
  );
  Ko.push("scrollEnd");
  function We(t, e) {
    Th.set(t, e), Aa(e, [t]);
  }
  var hb = 0;
  function On(t, e) {
    if (t.name != null && t.name !== "auto") return t.name;
    if (e.autoName !== null) return e.autoName;
    t = en.identifierPrefix;
    var n = hb++;
    return t = "_" + t + "t_" + n.toString(32) + "_", e.autoName = t;
  }
  function xh(t) {
    if (t == null || typeof t == "string")
      return t;
    var e = null, n = wi;
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
    return t = xh(t), e = xh(e), e == null ? t === "auto" ? null : t : e === "auto" ? null : e;
  }
  var Ds = typeof reportError == "function" ? reportError : function(t) {
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
      u !== 0 && Eh(n, s, u);
    }
  }
  function Ns(t, e, n, a) {
    Ye[fi++] = t, Ye[fi++] = e, Ye[fi++] = n, Ye[fi++] = a, Jo |= a, t.lanes |= a, t = t.alternate, t !== null && (t.lanes |= a);
  }
  function ko(t, e, n, a) {
    return Ns(t, e, n, a), ws(t);
  }
  function Da(t, e) {
    return Ns(t, null, null, e), ws(t);
  }
  function Eh(t, e, n) {
    t.lanes |= n;
    var a = t.alternate;
    a !== null && (a.lanes |= n);
    for (var s = !1, u = t.return; u !== null; )
      u.childLanes |= n, a = u.alternate, a !== null && (a.childLanes |= n), u.tag === 22 && (t = u.stateNode, t === null || t._visibility & 1 || (s = !0)), t = u, u = u.return;
    return t.tag === 3 ? (u = t.stateNode, s && e !== null && (s = 31 - Ne(n), t = u.hiddenUpdates, a = t[s], a === null ? t[s] = [e] : a.push(e), e.lane = n | 536870912), u) : null;
  }
  function ws(t) {
    if (50 < Vl)
      throw Vl = 0, bu = null, Error(o(185));
    for (var e = t.return; e !== null; )
      t = e, e = t.return;
    return t.tag === 3 ? t.stateNode : null;
  }
  var di = {};
  function mb(t, e, n, a) {
    this.tag = t, this.key = n, this.sibling = this.child = this.return = this.stateNode = this.type = this.elementType = null, this.index = 0, this.refCleanup = this.ref = null, this.pendingProps = e, this.dependencies = this.memoizedState = this.updateQueue = this.memoizedProps = null, this.mode = a, this.subtreeFlags = this.flags = 0, this.deletions = null, this.childLanes = this.lanes = 0, this.alternate = null;
  }
  function xe(t, e, n, a) {
    return new mb(t, e, n, a);
  }
  function Po(t) {
    return t = t.prototype, !(!t || !t.isReactComponent);
  }
  function wn(t, e) {
    var n = t.alternate;
    return n === null ? (n = xe(
      t.tag,
      e,
      t.key,
      t.mode
    ), n.elementType = t.elementType, n.type = t.type, n.stateNode = t.stateNode, n.alternate = t, t.alternate = n) : (n.pendingProps = e, n.type = t.type, n.flags = 0, n.subtreeFlags = 0, n.deletions = null), n.flags = t.flags & 1206910976, n.childLanes = t.childLanes, n.lanes = t.lanes, n.child = t.child, n.memoizedProps = t.memoizedProps, n.memoizedState = t.memoizedState, n.updateQueue = t.updateQueue, e = t.dependencies, n.dependencies = e === null ? null : { lanes: e.lanes, firstContext: e.firstContext }, n.sibling = t.sibling, n.index = t.index, n.ref = t.ref, n.refCleanup = t.refCleanup, n;
  }
  function Ah(t, e) {
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
      f = GS(
        t,
        n,
        on.current
      ) ? 26 : t === "html" || t === "head" || t === "body" ? 27 : 5;
    else
      t: switch (a) {
        case Qt:
          return t = xe(31, n, e, s), t.elementType = Qt, t.lanes = u, t;
        case yt:
          return Oa(n.children, s, u, e);
        case ot:
          f = 8, s |= 24;
          break;
        case $t:
          return t = xe(12, n, e, s | 2), t.elementType = $t, t.lanes = u, t;
        case tt:
          return t = xe(13, n, e, s), t.elementType = tt, t.lanes = u, t;
        case B:
          return t = xe(19, n, e, s), t.elementType = B, t.lanes = u, t;
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
              case Ct:
                f = 10;
                break t;
              case Zt:
                f = 9;
                break t;
              case Y:
                f = 11;
                break t;
              case at:
                f = 14;
                break t;
              case ft:
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
  function Mh(t) {
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
  var Ch = /* @__PURE__ */ new WeakMap();
  function qe(t, e) {
    if (typeof t == "object" && t !== null) {
      var n = Ch.get(t);
      return n !== void 0 ? n : (e = {
        value: t,
        source: e,
        stack: Sd(e)
      }, Ch.set(t, e), e);
    }
    return {
      value: t,
      source: e,
      stack: Sd(e)
    };
  }
  var hi = [], mi = 0, zs = null, hl = 0, Ge = [], Xe = 0, Kn = null, cn = 1, fn = "";
  function Rn(t, e) {
    hi[mi++] = hl, hi[mi++] = zs, zs = t, hl = e;
  }
  function Dh(t, e, n) {
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
  function _s(t) {
    t.return !== null && (Rn(t, 1), Dh(t, 1, 0));
  }
  function Io(t) {
    for (; t === zs; )
      zs = hi[--mi], hi[mi] = null, hl = hi[--mi], hi[mi] = null;
    for (; t === Kn; )
      Kn = Ge[--Xe], Ge[Xe] = null, fn = Ge[--Xe], Ge[Xe] = null, cn = Ge[--Xe], Ge[Xe] = null;
  }
  function Oh(t, e) {
    Ge[Xe++] = cn, Ge[Xe++] = fn, Ge[Xe++] = Kn, cn = e.id, fn = e.overflow, Kn = t;
  }
  var ee = null, Ut = null, ht = !1, Jn = null, Ze = !1, $o = Error(o(519));
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
  function Nh(t) {
    var e = t.stateNode, n = t.type, a = t.memoizedProps;
    switch (e[le] = t, e[Te] = a, n) {
      case "dialog":
        pt("cancel", e), pt("close", e);
        break;
      case "iframe":
      case "object":
      case "embed":
        pt("load", e);
        break;
      case "video":
      case "audio":
        for (n = 0; n < Ul.length; n++)
          pt(Ul[n], e);
        break;
      case "source":
        pt("error", e);
        break;
      case "img":
      case "image":
      case "link":
        pt("error", e), pt("load", e);
        break;
      case "details":
        pt("toggle", e);
        break;
      case "input":
        pt("invalid", e), qd(
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
        pt("invalid", e);
        break;
      case "textarea":
        pt("invalid", e), Xd(e, a.value, a.defaultValue, a.children);
    }
    n = a.children, typeof n != "string" && typeof n != "number" && typeof n != "bigint" || e.textContent === "" + n || a.suppressHydrationWarning === !0 || Fp(e.textContent, n) ? (a.popover != null && (pt("beforetoggle", e), pt("toggle", e)), a.onScroll != null && pt("scroll", e), a.onScrollEnd != null && pt("scrollend", e), a.onClick != null && (e.onclick = rn), e = !0) : e = !1, e || kn(t, !0);
  }
  function Vs(t) {
    for (ee = t.return; ee; )
      switch (ee.tag) {
        case 5:
        case 31:
        case 13:
          Ze = !1;
          return;
        case 27:
        case 3:
          Ze = !0;
          return;
        default:
          ee = ee.return;
      }
  }
  function pi(t) {
    if (t !== ee) return !1;
    if (!ht) return Vs(t), ht = !0, !1;
    var e = t.tag, n;
    if ((n = e !== 3 && e !== 27) && ((n = e === 5) && (n = t.type, n = !(n !== "form" && n !== "button") || Nc(t.type, t.memoizedProps)), n = !n), n && Ut && kn(t), Vs(t), e === 13) {
      if (t = t.memoizedState, t = t !== null ? t.dehydrated : null, !t) throw Error(o(317));
      Ut = py(t);
    } else if (e === 31) {
      if (t = t.memoizedState, t = t !== null ? t.dehydrated : null, !t) throw Error(o(317));
      Ut = py(t);
    } else
      e === 27 ? (e = Ut, ca(t.type) ? (t = Lc, Lc = null, Ut = t) : Ut = e) : Ut = ee ? Ke(t.stateNode.nextSibling) : null;
    return !0;
  }
  function Na() {
    Ut = ee = null, ht = !1;
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
  var er = un(null), wa = null, zn = null;
  function Pn(t, e, n) {
    jt(er, e._currentValue), e._currentValue = n;
  }
  function _n(t) {
    t._currentValue = er.current, ie(er);
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
  function za(t) {
    wa = t, zn = null, t = t.dependencies, t !== null && (t.firstContext = null);
  }
  function se(t) {
    return wh(wa, t);
  }
  function Bs(t, e) {
    return wa === null && za(t), wh(t, e);
  }
  function wh(t, e) {
    var n = e._currentValue;
    if (e = { context: e, memoizedValue: n, next: null }, zn === null) {
      if (t === null) throw Error(o(308));
      zn = e, t.dependencies = { lanes: 0, firstContext: e }, t.flags |= 524288;
    } else zn = zn.next = e;
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
  }, yb = i.unstable_scheduleCallback, gb = i.unstable_NormalPriority, Kt = {
    $$typeof: Ct,
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
  function pl(t) {
    t.refCount--, t.refCount === 0 && yb(gb, function() {
      t.controller.abort();
    });
  }
  function Rh(t, e) {
    if ((t.pendingLanes & 4194048) !== 0) {
      var n = t.transitionTypes;
      for (n === null && (n = t.transitionTypes = []), t = 0; t < e.length; t++) {
        var a = e[t];
        n.indexOf(a) === -1 && n.push(a);
      }
    }
  }
  var yl = null;
  function vb(t) {
    var e = t.transitionTypes;
    return t.transitionTypes = null, e;
  }
  var gl = null, ir = 0, _a = 0, yi = null;
  function bb(t, e) {
    if (gl === null) {
      var n = gl = [];
      ir = 0, _a = Sc(), yi = {
        status: "pending",
        value: void 0,
        then: function(a) {
          n.push(a);
        }
      };
    }
    return ir++, e.then(zh, zh), e;
  }
  function zh() {
    if (--ir === 0 && (yl = null, gl !== null)) {
      yi !== null && (yi.status = "fulfilled");
      var t = gl;
      gl = null, _a = 0, yi = null;
      for (var e = 0; e < t.length; e++) (0, t[e])();
    }
  }
  function Sb(t, e) {
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
  var _h = I.S;
  I.S = function(t, e) {
    if (Mp = De(), typeof e == "object" && e !== null && typeof e.then == "function" && bb(t, e), yl !== null)
      for (var n = Vi; n !== null; )
        Rh(n, yl), n = n.next;
    if (n = t.types, n !== null) {
      for (var a = Vi; a !== null; )
        Rh(a, n), a = a.next;
      if (_a !== 0) {
        a = yl, a === null && (a = yl = []);
        for (var s = 0; s < n.length; s++) {
          var u = n[s];
          a.indexOf(u) === -1 && a.push(u);
        }
      }
    }
    _h !== null && _h(t, e);
  };
  var Va = un(null);
  function lr() {
    var t = Va.current;
    return t !== null ? t : zt.pooledCache;
  }
  function Ls(t, e) {
    e === null ? jt(Va, Va.current) : jt(Va, e.pool);
  }
  function Vh() {
    var t = lr();
    return t === null ? null : { parent: Kt._currentValue, pool: t };
  }
  var gi = Error(o(460)), sr = Error(o(474)), Hs = Error(o(542)), Ys = { then: function() {
  } };
  function jh(t) {
    return t = t.status, t === "fulfilled" || t === "rejected";
  }
  function Uh(t, e, n) {
    switch (n = t[n], n === void 0 ? t.push(e) : n !== e && (e.then(rn, rn), e = n), e.status) {
      case "fulfilled":
        return e.value;
      case "rejected":
        throw t = e.reason, Lh(t), t === void 0 && !("reason" in e) ? Error(o(600)) : t;
      default:
        if (typeof e.status == "string") e.then(rn, rn);
        else {
          if (t = zt, t !== null && 100 < t.shellSuspendCounter)
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
            throw t = e.reason, Lh(t), t;
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
  function Bh() {
    if (Ua === null) throw Error(o(459));
    var t = Ua;
    return Ua = null, t;
  }
  function Lh(t) {
    if (t === gi || t === Hs)
      throw Error(o(483));
  }
  var vi = null, vl = 0;
  function qs(t) {
    var e = vl;
    return vl += 1, vi === null && (vi = []), Uh(vi, t, e);
  }
  function Fn(t, e) {
    e = e.props.ref, t.ref = e !== void 0 ? e : null;
  }
  function Gs(t, e) {
    throw e.$$typeof === Z ? Error(o(525)) : (t = Object.prototype.toString.call(e), Error(
      o(
        31,
        t === "[object Object]" ? "object with keys {" + Object.keys(e).join(", ") + "}" : t
      )
    ));
  }
  function Hh(t) {
    function e(M, x) {
      if (t) {
        var D = M.deletions;
        D === null ? (M.deletions = [x], M.flags |= 16) : D.push(x);
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
      return M = wn(M, x), M.index = 0, M.sibling = null, M;
    }
    function u(M, x, D) {
      return M.index = D, t ? (D = M.alternate, D !== null ? (D = D.index, D < x ? (M.flags |= 2, x) : D) : (M.flags |= 134217730, x)) : (M.flags |= 1048576, x);
    }
    function f(M) {
      return t && M.alternate === null && (M.flags |= 134217730), M;
    }
    function m(M, x, D, z) {
      return x === null || x.tag !== 6 ? (x = Fo(D, M.mode, z), x.return = M, x) : (x = s(x, D), x.return = M, x);
    }
    function S(M, x, D, z) {
      var k = D.type;
      return k === yt ? (M = N(
        M,
        x,
        D.props.children,
        z,
        D.key
      ), Fn(M, D), M) : x !== null && (x.elementType === k || typeof k == "object" && k !== null && k.$$typeof === ft && ja(k) === x.type) ? (x = s(x, D.props), Fn(x, D), x.return = M, x) : (x = Rs(
        D.type,
        D.key,
        D.props,
        null,
        M.mode,
        z
      ), Fn(x, D), x.return = M, x);
    }
    function C(M, x, D, z) {
      return x === null || x.tag !== 4 || x.stateNode.containerInfo !== D.containerInfo || x.stateNode.implementation !== D.implementation ? (x = Wo(D, M.mode, z), x.return = M, x) : (x = s(x, D.children || []), x.return = M, x);
    }
    function N(M, x, D, z, k) {
      return x === null || x.tag !== 7 ? (x = Oa(
        D,
        M.mode,
        z,
        k
      ), x.return = M, x) : (x = s(x, D), x.return = M, x);
    }
    function _(M, x, D) {
      if (typeof x == "string" && x !== "" || typeof x == "number" || typeof x == "bigint")
        return x = Fo(
          "" + x,
          M.mode,
          D
        ), x.return = M, x;
      if (typeof x == "object" && x !== null) {
        switch (x.$$typeof) {
          case Mt:
            return D = Rs(
              x.type,
              x.key,
              x.props,
              null,
              M.mode,
              D
            ), Fn(D, x), D.return = M, D;
          case W:
            return x = Wo(
              x,
              M.mode,
              D
            ), x.return = M, x;
          case ft:
            return x = ja(x), _(M, x, D);
        }
        if (Et(x) || nt(x))
          return x = Oa(
            x,
            M.mode,
            D,
            null
          ), x.return = M, x;
        if (typeof x.then == "function")
          return _(M, qs(x), D);
        if (x.$$typeof === Ct)
          return _(
            M,
            Bs(M, x),
            D
          );
        Gs(M, x);
      }
      return null;
    }
    function A(M, x, D, z) {
      var k = x !== null ? x.key : null;
      if (typeof D == "string" && D !== "" || typeof D == "number" || typeof D == "bigint")
        return k !== null ? null : m(M, x, "" + D, z);
      if (typeof D == "object" && D !== null) {
        switch (D.$$typeof) {
          case Mt:
            return D.key === k ? S(M, x, D, z) : null;
          case W:
            return D.key === k ? C(M, x, D, z) : null;
          case ft:
            return D = ja(D), A(M, x, D, z);
        }
        if (Et(D) || nt(D))
          return k !== null ? null : N(M, x, D, z, null);
        if (typeof D.then == "function")
          return A(
            M,
            x,
            qs(D),
            z
          );
        if (D.$$typeof === Ct)
          return A(
            M,
            x,
            Bs(M, D),
            z
          );
        Gs(M, D);
      }
      return null;
    }
    function O(M, x, D, z, k) {
      if (typeof z == "string" && z !== "" || typeof z == "number" || typeof z == "bigint")
        return M = M.get(D) || null, m(x, M, "" + z, k);
      if (typeof z == "object" && z !== null) {
        switch (z.$$typeof) {
          case Mt:
            return M = M.get(
              z.key === null ? D : z.key
            ) || null, S(x, M, z, k);
          case W:
            return M = M.get(
              z.key === null ? D : z.key
            ) || null, C(x, M, z, k);
          case ft:
            return z = ja(z), O(
              M,
              x,
              D,
              z,
              k
            );
        }
        if (Et(z) || nt(z))
          return M = M.get(D) || null, N(x, M, z, k, null);
        if (typeof z.then == "function")
          return O(
            M,
            x,
            D,
            qs(z),
            k
          );
        if (z.$$typeof === Ct)
          return O(
            M,
            x,
            D,
            Bs(x, z),
            k
          );
        Gs(x, z);
      }
      return null;
    }
    function G(M, x, D, z) {
      for (var k = null, vt = null, $ = x, lt = x = 0, Pt = null; $ !== null && lt < D.length; lt++) {
        $.index > lt ? (Pt = $, $ = null) : Pt = $.sibling;
        var bt = A(
          M,
          $,
          D[lt],
          z
        );
        if (bt === null) {
          $ === null && ($ = Pt);
          break;
        }
        t && $ && bt.alternate === null && e(M, $), x = u(bt, x, lt), vt === null ? k = bt : vt.sibling = bt, vt = bt, $ = Pt;
      }
      if (lt === D.length)
        return n(M, $), ht && Rn(M, lt), k;
      if ($ === null) {
        for (; lt < D.length; lt++)
          $ = _(M, D[lt], z), $ !== null && (x = u(
            $,
            x,
            lt
          ), vt === null ? k = $ : vt.sibling = $, vt = $);
        return ht && Rn(M, lt), k;
      }
      for ($ = a($); lt < D.length; lt++)
        Pt = O(
          $,
          M,
          lt,
          D[lt],
          z
        ), Pt !== null && (t && (bt = Pt.alternate, bt !== null && $.delete(bt.key === null ? lt : bt.key)), x = u(
          Pt,
          x,
          lt
        ), vt === null ? k = Pt : vt.sibling = Pt, vt = Pt);
      return t && $.forEach(function(pa) {
        return e(M, pa);
      }), ht && Rn(M, lt), k;
    }
    function P(M, x, D, z) {
      if (D == null) throw Error(o(151));
      for (var k = null, vt = null, $ = x, lt = x = 0, Pt = null, bt = D.next(); $ !== null && !bt.done; lt++, bt = D.next()) {
        $.index > lt ? (Pt = $, $ = null) : Pt = $.sibling;
        var pa = A(M, $, bt.value, z);
        if (pa === null) {
          $ === null && ($ = Pt);
          break;
        }
        t && $ && pa.alternate === null && e(M, $), x = u(pa, x, lt), vt === null ? k = pa : vt.sibling = pa, vt = pa, $ = Pt;
      }
      if (bt.done)
        return n(M, $), ht && Rn(M, lt), k;
      if ($ === null) {
        for (; !bt.done; lt++, bt = D.next())
          bt = _(M, bt.value, z), bt !== null && (x = u(bt, x, lt), vt === null ? k = bt : vt.sibling = bt, vt = bt);
        return ht && Rn(M, lt), k;
      }
      for ($ = a($); !bt.done; lt++, bt = D.next())
        bt = O($, M, lt, bt.value, z), bt !== null && (t && (Pt = bt.alternate, Pt !== null && $.delete(
          Pt.key === null ? lt : Pt.key
        )), x = u(bt, x, lt), vt === null ? k = bt : vt.sibling = bt, vt = bt);
      return t && $.forEach(function(tT) {
        return e(M, tT);
      }), ht && Rn(M, lt), k;
    }
    function ct(M, x, D, z) {
      if (typeof D == "object" && D !== null && D.type === yt && D.key === null && D.props.ref === void 0 && (D = D.props.children), typeof D == "object" && D !== null) {
        switch (D.$$typeof) {
          case Mt:
            t: {
              for (var k = D.key; x !== null; ) {
                if (x.key === k) {
                  if (k = D.type, k === yt) {
                    if (x.tag === 7) {
                      n(
                        M,
                        x.sibling
                      ), z = s(
                        x,
                        D.props.children
                      ), Fn(z, D), z.return = M, M = z;
                      break t;
                    }
                  } else if (x.elementType === k || typeof k == "object" && k !== null && k.$$typeof === ft && ja(k) === x.type) {
                    n(
                      M,
                      x.sibling
                    ), z = s(x, D.props), Fn(z, D), z.return = M, M = z;
                    break t;
                  }
                  n(M, x);
                  break;
                } else e(M, x);
                x = x.sibling;
              }
              D.type === yt ? (z = Oa(
                D.props.children,
                M.mode,
                z,
                D.key
              ), Fn(z, D), z.return = M, M = z) : (z = Rs(
                D.type,
                D.key,
                D.props,
                null,
                M.mode,
                z
              ), Fn(z, D), z.return = M, M = z);
            }
            return f(M);
          case W:
            t: {
              for (k = D.key; x !== null; ) {
                if (x.key === k)
                  if (x.tag === 4 && x.stateNode.containerInfo === D.containerInfo && x.stateNode.implementation === D.implementation) {
                    n(
                      M,
                      x.sibling
                    ), z = s(x, D.children || []), z.return = M, M = z;
                    break t;
                  } else {
                    n(M, x);
                    break;
                  }
                else e(M, x);
                x = x.sibling;
              }
              z = Wo(D, M.mode, z), z.return = M, M = z;
            }
            return f(M);
          case ft:
            return D = ja(D), ct(
              M,
              x,
              D,
              z
            );
        }
        if (Et(D))
          return G(
            M,
            x,
            D,
            z
          );
        if (nt(D)) {
          if (k = nt(D), typeof k != "function") throw Error(o(150));
          return D = k.call(D), P(
            M,
            x,
            D,
            z
          );
        }
        if (typeof D.then == "function")
          return ct(
            M,
            x,
            qs(D),
            z
          );
        if (D.$$typeof === Ct)
          return ct(
            M,
            x,
            Bs(M, D),
            z
          );
        Gs(M, D);
      }
      return typeof D == "string" && D !== "" || typeof D == "number" || typeof D == "bigint" ? (D = "" + D, x !== null && x.tag === 6 ? (n(M, x.sibling), z = s(x, D), z.return = M, M = z) : (n(M, x), z = Fo(D, M.mode, z), z.return = M, M = z), f(M)) : n(M, x);
    }
    return function(M, x, D, z) {
      try {
        vl = 0;
        var k = ct(
          M,
          x,
          D,
          z
        );
        return vi = null, k;
      } catch ($) {
        if ($ === gi || $ === Hs) throw $;
        var vt = xe(29, $, null, M.mode);
        return vt.lanes = z, vt.return = M, vt;
      }
    };
  }
  var Ba = Hh(!0), Yh = Hh(!1), Wn = !1;
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
    if (a = a.shared, (At & 2) !== 0) {
      var s = a.pending;
      return s === null ? e.next = e : (e.next = s.next, s.next = e), a.pending = e, e = ws(t), Eh(t, null, n), e;
    }
    return Ns(t, a, e, n), ws(t);
  }
  function bl(t, e, n) {
    if (e = e.updateQueue, e !== null && (e = e.shared, (n & 4194048) !== 0)) {
      var a = e.lanes;
      a &= t.pendingLanes, n |= a, e.lanes = n, Dd(t, n);
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
      var t = yi;
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
      var S = m, C = S.next;
      S.next = null, f === null ? u = C : f.next = C, f = S;
      var N = t.alternate;
      N !== null && (N = N.updateQueue, m = N.lastBaseUpdate, m !== f && (m === null ? N.firstBaseUpdate = C : m.next = C, N.lastBaseUpdate = S));
    }
    if (u !== null) {
      var _ = s.baseState;
      f = 0, N = C = S = null, m = u;
      do {
        var A = m.lane & -536870913, O = A !== m.lane;
        if (O ? (gt & A) === A : (a & A) === A) {
          A !== 0 && A === _a && (cr = !0), N !== null && (N = N.next = {
            lane: 0,
            tag: m.tag,
            payload: m.payload,
            callback: null,
            next: null
          });
          t: {
            var G = t, P = m;
            A = e;
            var ct = n;
            switch (P.tag) {
              case 1:
                if (G = P.payload, typeof G == "function") {
                  _ = G.call(ct, _, A);
                  break t;
                }
                _ = G;
                break t;
              case 3:
                G.flags = G.flags & -65537 | 128;
              case 0:
                if (G = P.payload, A = typeof G == "function" ? G.call(ct, _, A) : G, A == null) break t;
                _ = J({}, _, A);
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
          }, N === null ? (C = N = O, S = _) : N = N.next = O, f |= A;
        if (m = m.next, m === null) {
          if (m = s.shared.pending, m === null)
            break;
          O = m, m = O.next, O.next = null, s.lastBaseUpdate = O, s.shared.pending = null;
        }
      } while (!0);
      N === null && (S = _), s.baseState = S, s.firstBaseUpdate = C, s.lastBaseUpdate = N, u === null && (s.shared.lanes = 0), sa |= f, t.lanes = f, t.memoizedState = _;
    }
  }
  function qh(t, e) {
    if (typeof t != "function")
      throw Error(o(191, t));
    t.call(e);
  }
  function Gh(t, e) {
    var n = t.callbacks;
    if (n !== null)
      for (t.callbacks = null, t = 0; t < n.length; t++)
        qh(n[t], e);
  }
  var ta = un(null), Xs = un(0);
  function Xh(t, e) {
    t = Ln, jt(Xs, t), jt(ta, e), Ln = t | e.baseLanes;
  }
  function fr() {
    jt(Xs, Ln), jt(ta, ta.current);
  }
  function dr() {
    Ln = Xs.current, ie(ta), ie(Xs);
  }
  var ue = un(null), me = null;
  function ea(t) {
    var e = t.alternate;
    jt(oe, oe.current & 1), jt(ue, t), me === null && (e === null || ta.current !== null || e.memoizedState !== null) && (me = t);
  }
  function hr(t) {
    jt(oe, oe.current), jt(ue, t), me === null && (me = t);
  }
  function Zh(t) {
    t.tag === 22 ? (jt(oe, oe.current), jt(ue, t), me === null && (me = t)) : na();
  }
  function na() {
    jt(oe, oe.current), jt(ue, ue.current);
  }
  function ze(t) {
    ie(ue), me === t && (me = null), ie(oe);
  }
  var oe = un(0);
  function xl(t, e) {
    jt(ue, ue.current), jt(oe, e);
  }
  function mr(t) {
    ie(oe), ie(ue), me === t && (me = null);
  }
  function Zs(t) {
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
  var Vn = 0, rt = null, Rt = null, Jt = null, Qs = !1, bi = !1, La = !1, Ks = 0, El = 0, Si = null, Tb = 0;
  function Yt() {
    throw Error(o(321));
  }
  function pr(t, e) {
    if (e === null) return !1;
    for (var n = 0; n < e.length && n < t.length; n++)
      if (!Re(t[n], e[n])) return !1;
    return !0;
  }
  function yr(t, e, n, a, s, u) {
    return Vn = u, rt = e, e.memoizedState = null, e.updateQueue = null, e.lanes = 0, I.H = t === null || t.memoizedState === null ? Dm : Om, La = !1, u = n(a, s), La = !1, bi && (u = Kh(
      e,
      n,
      a,
      s
    )), Qh(t), u;
  }
  function Qh(t) {
    I.H = $s;
    var e = Rt !== null && Rt.next !== null;
    if (Vn = 0, Jt = Rt = rt = null, Qs = !1, El = 0, Si = null, e) throw Error(o(300));
    t === null || kt || (t = t.dependencies, t !== null && Us(t) && (kt = !0));
  }
  function Kh(t, e, n, a) {
    rt = t;
    var s = 0;
    do {
      if (bi && (Si = null), El = 0, bi = !1, 25 <= s) throw Error(o(301));
      if (s += 1, Jt = Rt = null, t.updateQueue != null) {
        var u = t.updateQueue;
        u.lastEffect = null, u.events = null, u.stores = null, u.memoCache != null && (u.memoCache.index = 0);
      }
      I.H = Nb, u = e(n, a);
    } while (bi);
    return u;
  }
  function xb() {
    var t = I.H, e = t.useState()[0];
    return e = typeof e.then == "function" ? Al(e) : e, t = t.useState()[0], (Rt !== null ? Rt.memoizedState : null) !== t && (rt.flags |= 1024), e;
  }
  function gr() {
    var t = Ks !== 0;
    return Ks = 0, t;
  }
  function vr(t, e, n) {
    e.updateQueue = t.updateQueue, e.flags &= -2053, t.lanes &= ~n;
  }
  function br(t) {
    if (Qs) {
      for (t = t.memoizedState; t !== null; ) {
        var e = t.queue;
        e !== null && (e.pending = null), t = t.next;
      }
      Qs = !1;
    }
    Vn = 0, Jt = Rt = rt = null, bi = !1, El = Ks = 0, Si = null;
  }
  function ye() {
    var t = {
      memoizedState: null,
      baseState: null,
      baseQueue: null,
      queue: null,
      next: null
    };
    return Jt === null ? rt.memoizedState = Jt = t : Jt = Jt.next = t, Jt;
  }
  function Xt() {
    if (Rt === null) {
      var t = rt.alternate;
      t = t !== null ? t.memoizedState : null;
    } else t = Rt.next;
    var e = Jt === null ? rt.memoizedState : Jt.next;
    if (e !== null)
      Jt = e, Rt = t;
    else {
      if (t === null)
        throw rt.alternate === null ? Error(o(467)) : Error(o(310));
      Rt = t, t = {
        memoizedState: Rt.memoizedState,
        baseState: Rt.baseState,
        baseQueue: Rt.baseQueue,
        queue: Rt.queue,
        next: null
      }, Jt === null ? rt.memoizedState = Jt = t : Jt = Jt.next = t;
    }
    return Jt;
  }
  function Js() {
    return { lastEffect: null, events: null, stores: null, memoCache: null };
  }
  function Al(t) {
    var e = El;
    return El += 1, Si === null && (Si = []), t = Uh(Si, t, e), e = rt, (Jt === null ? e.memoizedState : Jt.next) === null && (e = e.alternate, I.H = e === null || e.memoizedState === null ? Dm : Om), t;
  }
  function ks(t) {
    if (t !== null && typeof t == "object") {
      if (typeof t.then == "function") return Al(t);
      if (t.$$typeof === L) return;
      if (t.$$typeof === Ct) return se(t);
    }
    throw Error(o(438, String(t)));
  }
  function Sr(t) {
    var e = null, n = rt.updateQueue;
    if (n !== null && (e = n.memoCache), e == null) {
      var a = rt.alternate;
      a !== null && (a = a.updateQueue, a !== null && (a = a.memoCache, a != null && (e = {
        data: a.data.map(function(s) {
          return s.slice();
        }),
        index: 0
      })));
    }
    if (e == null && (e = { data: [], index: 0 }), n === null && (n = Js(), rt.updateQueue = n), n.memoCache = e, n = e.data[e.index], n === void 0)
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
      var m = f = null, S = null, C = e, N = !1;
      do {
        var _ = C.lane & -536870913;
        if (_ !== C.lane ? (gt & _) === _ : (Vn & _) === _) {
          var A = C.revertLane;
          if (A === 0)
            S !== null && (S = S.next = {
              lane: 0,
              revertLane: 0,
              gesture: null,
              action: C.action,
              hasEagerState: C.hasEagerState,
              eagerState: C.eagerState,
              next: null
            }), _ === _a && (N = !0);
          else if ((Vn & A) === A) {
            C = C.next, A === _a && (N = !0);
            continue;
          } else
            _ = {
              lane: 0,
              revertLane: C.revertLane,
              gesture: null,
              action: C.action,
              hasEagerState: C.hasEagerState,
              eagerState: C.eagerState,
              next: null
            }, S === null ? (m = S = _, f = u) : S = S.next = _, rt.lanes |= A, sa |= A;
          _ = C.action, La && n(u, _), u = C.hasEagerState ? C.eagerState : n(u, _);
        } else
          A = {
            lane: _,
            revertLane: C.revertLane,
            gesture: C.gesture,
            action: C.action,
            hasEagerState: C.hasEagerState,
            eagerState: C.eagerState,
            next: null
          }, S === null ? (m = S = A, f = u) : S = S.next = A, rt.lanes |= _, sa |= _;
        C = C.next;
      } while (C !== null && C !== e);
      if (S === null ? f = u : S.next = m, !Re(u, t.memoizedState) && (kt = !0, N && (n = yi, n !== null)))
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
      Re(u, e.memoizedState) || (kt = !0), e.memoizedState = u, e.baseQueue === null && (e.baseState = u), n.lastRenderedState = u;
    }
    return [u, a];
  }
  function Jh(t, e, n) {
    var a = rt, s = Xt(), u = ht;
    if (u) {
      if (n === void 0) throw Error(o(407));
      n = n();
    } else n = e();
    var f = !Re(
      (Rt || s).memoizedState,
      n
    );
    if (f && (s.memoizedState = n, kt = !0), s = s.queue, Mr(Fh.bind(null, a, s, t), [
      t
    ]), t = s.getSnapshot !== e || f || Jt !== null && (Jt.memoizedState.tag & 1) !== 0, Ti(
      t ? 9 : 8,
      { destroy: void 0 },
      Ph.bind(null, a, s, n, e),
      null
    ), t) {
      if (a.flags |= 2048, zt === null) throw Error(o(349));
      u || (Vn & 127) !== 0 || kh(a, e, n);
    }
    return n;
  }
  function kh(t, e, n) {
    t.flags |= 16384, t = { getSnapshot: e, value: n }, e = rt.updateQueue, e === null ? (e = Js(), rt.updateQueue = e, e.stores = [t]) : (n = e.stores, n === null ? e.stores = [t] : n.push(t));
  }
  function Ph(t, e, n, a) {
    e.value = n, e.getSnapshot = a, Wh(e) && Ih(t);
  }
  function Fh(t, e, n) {
    return n(function() {
      Wh(e) && Ih(t);
    });
  }
  function Wh(t) {
    var e = t.getSnapshot;
    t = t.value;
    try {
      var n = e();
      return !Re(t, n);
    } catch {
      return !0;
    }
  }
  function Ih(t) {
    var e = Da(t, 2);
    e !== null && Ce(e, t, 2);
  }
  function Er(t) {
    var e = ye();
    if (typeof t == "function") {
      var n = t;
      if (t = n(), La) {
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
  function $h(t, e, n, a) {
    return t.baseState = n, Tr(
      t,
      Rt,
      typeof a == "function" ? a : jn
    );
  }
  function Eb(t, e, n, a, s) {
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
      I.T !== null ? n(!0) : u.isTransition = !1, a(u), n = e.pending, n === null ? (u.next = e.pending = u, tm(e, u)) : (u.next = n.next, e.pending = n.next = u);
    }
  }
  function tm(t, e) {
    var n = e.action, a = e.payload, s = t.state;
    if (e.isTransition) {
      var u = I.T, f = {};
      f.types = u !== null ? u.types : null, I.T = f;
      try {
        var m = n(s, a), S = I.S;
        S !== null && S(f, m), em(t, e, m);
      } catch (C) {
        Ar(t, e, C);
      } finally {
        u !== null && f.types !== null && (u.types = f.types), I.T = u;
      }
    } else
      try {
        u = n(s, a), em(t, e, u);
      } catch (C) {
        Ar(t, e, C);
      }
  }
  function em(t, e, n) {
    n !== null && typeof n == "object" && typeof n.then == "function" ? n.then(
      function(a) {
        nm(t, e, a);
      },
      function(a) {
        return Ar(t, e, a);
      }
    ) : nm(t, e, n);
  }
  function nm(t, e, n) {
    e.status = "fulfilled", e.value = n, am(e), t.state = n, e = t.pending, e !== null && (n = e.next, n === e ? t.pending = null : (n = n.next, e.next = n, tm(t, n)));
  }
  function Ar(t, e, n) {
    var a = t.pending;
    if (t.pending = null, a !== null) {
      a = a.next;
      do
        e.status = "rejected", e.reason = n, am(e), e = e.next;
      while (e !== a);
    }
    t.action = null;
  }
  function am(t) {
    t = t.listeners;
    for (var e = 0; e < t.length; e++) (0, t[e])();
  }
  function im(t, e) {
    return e;
  }
  function lm(t, e) {
    if (ht) {
      var n = zt.formState;
      if (n !== null) {
        t: {
          var a = rt;
          if (ht) {
            if (Ut) {
              e: {
                for (var s = Ut, u = Ze; s.nodeType !== 8; ) {
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
    return n = ye(), n.memoizedState = n.baseState = e, a = {
      pending: null,
      lanes: 0,
      dispatch: null,
      lastRenderedReducer: im,
      lastRenderedState: e
    }, n.queue = a, n = Am.bind(
      null,
      rt,
      a
    ), a.dispatch = n, a = Er(!1), u = wr.bind(
      null,
      rt,
      !1,
      a.queue
    ), a = ye(), s = {
      state: e,
      dispatch: null,
      action: t,
      pending: null
    }, a.queue = s, n = Eb.bind(
      null,
      rt,
      s,
      u,
      n
    ), s.dispatch = n, a.memoizedState = t, [e, n, !1];
  }
  function sm(t) {
    var e = Xt();
    return um(e, Rt, t);
  }
  function um(t, e, n) {
    if (e = Tr(
      t,
      e,
      im
    )[0], t = Ps(jn)[0], typeof e == "object" && e !== null && typeof e.then == "function")
      try {
        var a = Al(e);
      } catch (f) {
        throw f === gi ? Hs : f;
      }
    else a = e;
    e = Xt();
    var s = e.queue, u = s.dispatch;
    return n !== e.memoizedState && (rt.flags |= 2048, Ti(
      9,
      { destroy: void 0 },
      Ab.bind(null, s, n),
      null
    )), [a, u, t];
  }
  function Ab(t, e) {
    t.action = e;
  }
  function om(t) {
    var e = Xt(), n = Rt;
    if (n !== null)
      return um(e, n, t);
    Xt(), e = e.memoizedState, n = Xt();
    var a = n.queue.dispatch;
    return n.memoizedState = t, [e, a, !1];
  }
  function Ti(t, e, n, a) {
    return t = { tag: t, create: n, deps: a, inst: e, next: null }, e = rt.updateQueue, e === null && (e = Js(), rt.updateQueue = e), n = e.lastEffect, n === null ? e.lastEffect = t.next = t : (a = n.next, n.next = t, t.next = a, e.lastEffect = t), t;
  }
  function rm() {
    return Xt().memoizedState;
  }
  function Fs(t, e, n, a) {
    var s = ye();
    rt.flags |= t, s.memoizedState = Ti(
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
    Rt !== null && a !== null && pr(a, Rt.memoizedState.deps) ? s.memoizedState = Ti(e, u, n, a) : (rt.flags |= t, s.memoizedState = Ti(
      1 | e,
      u,
      n,
      a
    ));
  }
  function cm(t, e) {
    Fs(8390656, 8, t, e);
  }
  function Mr(t, e) {
    Ws(2048, 8, t, e);
  }
  function Mb(t) {
    rt.flags |= 4;
    var e = rt.updateQueue;
    if (e === null)
      e = Js(), rt.updateQueue = e, e.events = [t];
    else {
      var n = e.events;
      n === null ? e.events = [t] : n.push(t);
    }
  }
  function fm(t) {
    var e = Xt().memoizedState;
    return Mb({ ref: e, nextImpl: t }), function() {
      if ((At & 2) !== 0) throw Error(o(440));
      return e.impl.apply(void 0, arguments);
    };
  }
  function dm(t, e) {
    return Ws(4, 2, t, e);
  }
  function hm(t, e) {
    return Ws(4, 4, t, e);
  }
  function mm(t, e) {
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
  function pm(t, e, n) {
    n = n != null ? n.concat([t]) : null, Ws(4, 4, mm.bind(null, e, t), n);
  }
  function Cr() {
  }
  function ym(t, e) {
    var n = Xt();
    e = e === void 0 ? null : e;
    var a = n.memoizedState;
    return e !== null && pr(e, a[1]) ? a[0] : (n.memoizedState = [t, e], t);
  }
  function gm(t, e) {
    var n = Xt();
    e = e === void 0 ? null : e;
    var a = n.memoizedState;
    if (e !== null && pr(e, a[1]))
      return a[0];
    if (a = t(), La) {
      Xn(!0);
      try {
        t();
      } finally {
        Xn(!1);
      }
    }
    return n.memoizedState = [a, e], a;
  }
  function Dr(t, e, n) {
    return n === void 0 || (Vn & 1073741824) !== 0 && (gt & 261930) === 0 ? t.memoizedState = e : (t.memoizedState = n, t = Dp(), rt.lanes |= t, sa |= t, n);
  }
  function vm(t, e, n, a) {
    return Re(n, e) ? n : ta.current !== null ? (t = Dr(t, n, a), Re(t, e) || (kt = !0), t) : (Vn & 106) === 0 || (Vn & 1073741824) !== 0 && (gt & 261930) === 0 ? (kt = !0, t.memoizedState = n) : (t = Dp(), rt.lanes |= t, sa |= t, e);
  }
  function bm(t, e, n, a, s) {
    var u = st.p;
    st.p = u !== 0 && 8 > u ? u : 8;
    var f = I.T, m = {};
    m.types = f !== null ? f.types : null, I.T = m, wr(t, !1, e, n);
    try {
      var S = s(), C = I.S;
      if (C !== null && C(m, S), S !== null && typeof S == "object" && typeof S.then == "function") {
        var N = Sb(
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
    } catch (_) {
      Ml(
        t,
        e,
        { then: function() {
        }, status: "rejected", reason: _ },
        Ue()
      );
    } finally {
      st.p = u, f !== null && m.types !== null && (f.types = m.types), I.T = f;
    }
  }
  function Cb() {
  }
  function Or(t, e, n, a) {
    if (t.tag !== 5) throw Error(o(476));
    var s = Sm(t).queue;
    bm(
      t,
      s,
      e,
      An,
      n === null ? Cb : function() {
        return Tm(t), n(a);
      }
    );
  }
  function Sm(t) {
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
  function Tm(t) {
    var e = Sm(t);
    e.next === null && (e = t.alternate.memoizedState), Ml(
      t,
      e.next.queue,
      {},
      Ue()
    );
  }
  function Nr() {
    return se(Yi);
  }
  function xm() {
    return Xt().memoizedState;
  }
  function Em() {
    return Xt().memoizedState;
  }
  function Db(t) {
    for (var e = t.return; e !== null; ) {
      switch (e.tag) {
        case 24:
        case 3:
          var n = Ue();
          t = In(n);
          var a = $n(e, t, n);
          a !== null && (Ce(a, e, n), bl(a, e, n)), e = { cache: ar() }, t.payload = e;
          return;
      }
      e = e.return;
    }
  }
  function Ob(t, e, n) {
    var a = Ue();
    n = {
      lane: a,
      revertLane: 0,
      gesture: null,
      action: n,
      hasEagerState: !1,
      eagerState: null,
      next: null
    }, Is(t) ? Mm(e, n) : (n = ko(t, e, n, a), n !== null && (Ce(n, t, a), Cm(n, e, a)));
  }
  function Am(t, e, n) {
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
    if (Is(t)) Mm(e, s);
    else {
      var u = t.alternate;
      if (t.lanes === 0 && (u === null || u.lanes === 0) && (u = e.lastRenderedReducer, u !== null))
        try {
          var f = e.lastRenderedState, m = u(f, n);
          if (s.hasEagerState = !0, s.eagerState = m, Re(m, f))
            return Ns(t, e, s, 0), zt === null && Os(), !1;
        } catch {
        }
      if (n = ko(t, e, s, a), n !== null)
        return Ce(n, t, a), Cm(n, e, a), !0;
    }
    return !1;
  }
  function wr(t, e, n, a) {
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
      ), e !== null && Ce(e, t, 2);
  }
  function Is(t) {
    var e = t.alternate;
    return t === rt || e !== null && e === rt;
  }
  function Mm(t, e) {
    bi = Qs = !0;
    var n = t.pending;
    n === null ? e.next = e : (e.next = n.next, n.next = e), t.pending = e;
  }
  function Cm(t, e, n) {
    if ((n & 4194048) !== 0) {
      var a = e.lanes;
      a &= t.pendingLanes, n |= a, e.lanes = n, Dd(t, n);
    }
  }
  var $s = {
    readContext: se,
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
  }, Dm = {
    readContext: se,
    use: ks,
    useCallback: function(t, e) {
      return ye().memoizedState = [
        t,
        e === void 0 ? null : e
      ], t;
    },
    useContext: se,
    useEffect: cm,
    useImperativeHandle: function(t, e, n) {
      n = n != null ? n.concat([t]) : null, Fs(
        4194308,
        4,
        mm.bind(null, e, t),
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
      var n = ye();
      e = e === void 0 ? null : e;
      var a = t();
      if (La) {
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
      var a = ye();
      if (n !== void 0) {
        var s = n(e);
        if (La) {
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
      }, a.queue = t, t = t.dispatch = Ob.bind(
        null,
        rt,
        t
      ), [a.memoizedState, t];
    },
    useRef: function(t) {
      var e = ye();
      return t = { current: t }, e.memoizedState = t;
    },
    useState: function(t) {
      t = Er(t);
      var e = t.queue, n = Am.bind(null, rt, e);
      return e.dispatch = n, [t.memoizedState, n];
    },
    useDebugValue: Cr,
    useDeferredValue: function(t, e) {
      var n = ye();
      return Dr(n, t, e);
    },
    useTransition: function() {
      var t = Er(!1);
      return t = bm.bind(
        null,
        rt,
        t.queue,
        !0,
        !1
      ), ye().memoizedState = t, [!1, t];
    },
    useSyncExternalStore: function(t, e, n) {
      var a = rt, s = ye();
      if (ht) {
        if (n === void 0)
          throw Error(o(407));
        n = n();
      } else {
        if (n = e(), zt === null)
          throw Error(o(349));
        (gt & 127) !== 0 || kh(a, e, n);
      }
      s.memoizedState = n;
      var u = { value: n, getSnapshot: e };
      return s.queue = u, cm(Fh.bind(null, a, u, t), [
        t
      ]), a.flags |= 2048, Ti(
        9,
        { destroy: void 0 },
        Ph.bind(
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
      var t = ye(), e = zt.identifierPrefix;
      if (ht) {
        var n = fn, a = cn;
        n = (a & ~(1 << 32 - Ne(a) - 1)).toString(32) + n, e = "_" + e + "R_" + n, n = Ks++, 0 < n && (e += "H" + n.toString(32)), e += "_";
      } else
        n = Tb++, e = "_" + e + "r_" + n.toString(32) + "_";
      return t.memoizedState = e;
    },
    useHostTransitionStatus: Nr,
    useFormState: lm,
    useActionState: lm,
    useOptimistic: function(t) {
      var e = ye();
      e.memoizedState = e.baseState = t;
      var n = {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: null,
        lastRenderedState: null
      };
      return e.queue = n, e = wr.bind(
        null,
        rt,
        !0,
        n
      ), n.dispatch = e, [t, e];
    },
    useMemoCache: Sr,
    useCacheRefresh: function() {
      return ye().memoizedState = Db.bind(
        null,
        rt
      );
    },
    useEffectEvent: function(t) {
      var e = ye(), n = { impl: t };
      return e.memoizedState = n, function() {
        if ((At & 2) !== 0)
          throw Error(o(440));
        return n.impl.apply(void 0, arguments);
      };
    }
  }, Om = {
    readContext: se,
    use: ks,
    useCallback: ym,
    useContext: se,
    useEffect: Mr,
    useImperativeHandle: pm,
    useInsertionEffect: dm,
    useLayoutEffect: hm,
    useMemo: gm,
    useReducer: Ps,
    useRef: rm,
    useState: function() {
      return Ps(jn);
    },
    useDebugValue: Cr,
    useDeferredValue: function(t, e) {
      var n = Xt();
      return vm(
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
    useSyncExternalStore: Jh,
    useId: xm,
    useHostTransitionStatus: Nr,
    useFormState: sm,
    useActionState: sm,
    useOptimistic: function(t, e) {
      var n = Xt();
      return $h(n, Rt, t, e);
    },
    useMemoCache: Sr,
    useCacheRefresh: Em,
    useEffectEvent: fm
  }, Nb = {
    readContext: se,
    use: ks,
    useCallback: ym,
    useContext: se,
    useEffect: Mr,
    useImperativeHandle: pm,
    useInsertionEffect: dm,
    useLayoutEffect: hm,
    useMemo: gm,
    useReducer: xr,
    useRef: rm,
    useState: function() {
      return xr(jn);
    },
    useDebugValue: Cr,
    useDeferredValue: function(t, e) {
      var n = Xt();
      return Rt === null ? Dr(n, t, e) : vm(
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
    useSyncExternalStore: Jh,
    useId: xm,
    useHostTransitionStatus: Nr,
    useFormState: om,
    useActionState: om,
    useOptimistic: function(t, e) {
      var n = Xt();
      return Rt !== null ? $h(n, Rt, t, e) : (n.baseState = t, [t, n.queue.dispatch]);
    },
    useMemoCache: Sr,
    useCacheRefresh: Em,
    useEffectEvent: fm
  };
  function Rr(t, e, n, a) {
    e = t.memoizedState, n = n(a, e), n = n == null ? e : J({}, e, n), t.memoizedState = n, t.lanes === 0 && (t.updateQueue.baseState = n);
  }
  var zr = {
    enqueueSetState: function(t, e, n) {
      t = t._reactInternals;
      var a = Ue(), s = In(a);
      s.payload = e, n != null && (s.callback = n), e = $n(t, s, a), e !== null && (Ce(e, t, a), bl(e, t, a));
    },
    enqueueReplaceState: function(t, e, n) {
      t = t._reactInternals;
      var a = Ue(), s = In(a);
      s.tag = 1, s.payload = e, n != null && (s.callback = n), e = $n(t, s, a), e !== null && (Ce(e, t, a), bl(e, t, a));
    },
    enqueueForceUpdate: function(t, e) {
      t = t._reactInternals;
      var n = Ue(), a = In(n);
      a.tag = 2, e != null && (a.callback = e), e = $n(t, a, n), e !== null && (Ce(e, t, n), bl(e, t, n));
    }
  };
  function Nm(t, e, n, a, s, u, f) {
    return t = t.stateNode, typeof t.shouldComponentUpdate == "function" ? t.shouldComponentUpdate(a, u, f) : e.prototype && e.prototype.isPureReactComponent ? !fl(n, a) || !fl(s, u) : !0;
  }
  function wm(t, e, n, a) {
    t = e.state, typeof e.componentWillReceiveProps == "function" && e.componentWillReceiveProps(n, a), typeof e.UNSAFE_componentWillReceiveProps == "function" && e.UNSAFE_componentWillReceiveProps(n, a), e.state !== t && zr.enqueueReplaceState(e, e.state, null);
  }
  function Ha(t, e) {
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
  function Rm(t) {
    Ds(t);
  }
  function zm(t) {
    console.error(t);
  }
  function _m(t) {
    Ds(t);
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
  function Vm(t, e, n) {
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
  function _r(t, e, n) {
    return n = In(n), n.tag = 3, n.payload = { element: null }, n.callback = function() {
      tu(t, e);
    }, n;
  }
  function jm(t) {
    return t = In(t), t.tag = 3, t;
  }
  function Um(t, e, n, a) {
    var s = n.type.getDerivedStateFromError;
    if (typeof s == "function") {
      var u = a.value;
      t.payload = function() {
        return s(u);
      }, t.callback = function() {
        Vm(e, n, a);
      };
    }
    var f = n.stateNode;
    f !== null && typeof f.componentDidCatch == "function" && (t.callback = function() {
      Vm(e, n, a), typeof s != "function" && (ua === null ? ua = /* @__PURE__ */ new Set([this]) : ua.add(this));
      var m = a.stack;
      this.componentDidCatch(a.value, {
        componentStack: m !== null ? m : ""
      });
    });
  }
  function wb(t, e, n, a, s) {
    if (n.flags |= 32768, a !== null && typeof a == "object" && typeof a.then == "function") {
      if (e = n.alternate, e !== null && Ra(
        e,
        n,
        s,
        !0
      ), n = ue.current, n !== null) {
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
    if (ht)
      return e = ue.current, e !== null ? ((e.flags & 65536) === 0 && (e.flags |= 256), e.flags |= 65536, e.lanes = s, a !== $o && (t = Error(o(422), { cause: a }), ml(qe(t, n)))) : (a !== $o && (e = Error(o(423), {
        cause: a
      }), ml(
        qe(e, n)
      )), t = t.current.alternate, t.flags |= 65536, s &= -s, t.lanes |= s, a = qe(a, n), s = _r(
        t.stateNode,
        a,
        s
      ), rr(t, s), qt !== 4 && (qt = 2)), !1;
    var u = Error(o(520), { cause: a });
    if (u = qe(u, n), _l === null ? _l = [u] : _l.push(u), qt !== 4 && (qt = 2), e === null) return !0;
    a = qe(a, n), n = e;
    do {
      switch (n.tag) {
        case 3:
          return n.flags |= 65536, t = s & -s, n.lanes |= t, t = _r(n.stateNode, a, t), rr(n, t), !1;
        case 1:
          if (e = n.type, u = n.stateNode, (n.flags & 128) === 0 && (typeof e.getDerivedStateFromError == "function" || u !== null && typeof u.componentDidCatch == "function" && (ua === null || !ua.has(u))))
            return n.flags |= 65536, s &= -s, n.lanes |= s, s = jm(s), Um(
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
  var Vr = Error(o(461)), kt = !1;
  function Wt(t, e, n, a) {
    e.child = t === null ? Yh(e, null, n, a) : Ba(
      e,
      t.child,
      n,
      a
    );
  }
  function Bm(t, e, n, a, s) {
    n = n.render;
    var u = e.ref;
    if ("ref" in a) {
      var f = {};
      for (var m in a)
        m !== "ref" && (f[m] = a[m]);
    } else f = a;
    return za(e), a = yr(
      t,
      e,
      n,
      f,
      u,
      s
    ), m = gr(), t !== null && !kt ? (vr(t, e, s), Un(t, e, s)) : (ht && m && _s(e), e.flags |= 1, Wt(t, e, a, s), e.child);
  }
  function Lm(t, e, n, a, s) {
    if (t === null) {
      var u = n.type;
      return typeof u == "function" && !Po(u) && u.defaultProps === void 0 && n.compare === null ? (e.tag = 15, e.type = u, Hm(
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
    return e.flags |= 1, t = wn(u, a), t.ref = e.ref, t.return = e, e.child = t;
  }
  function Hm(t, e, n, a, s) {
    if (t !== null) {
      var u = t.memoizedProps;
      if (fl(u, a) && t.ref === e.ref)
        if (kt = !1, e.pendingProps = a = u, Gr(t, s))
          (t.flags & 131072) !== 0 && (kt = !0);
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
  function Ym(t, e, n, a) {
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
        return qm(
          t,
          e,
          u,
          n,
          a
        );
      }
      if ((n & 536870912) !== 0)
        e.memoizedState = { baseLanes: 0, cachePool: null }, t !== null && Ls(
          e,
          u !== null ? u.cachePool : null
        ), u !== null ? Xh(e, u) : fr(), Zh(e);
      else
        return a = e.lanes = 536870912, qm(
          t,
          e,
          u !== null ? u.baseLanes | n : n,
          n,
          a
        );
    } else
      u !== null ? (Ls(e, u.cachePool), Xh(e, u), na(), e.memoizedState = null) : (t !== null && Ls(e, null), fr(), na());
    return Wt(t, e, s, n), e.child;
  }
  function Cl(t, e) {
    return t !== null && t.tag === 22 || e.stateNode !== null || (e.stateNode = {
      _visibility: 1,
      _pendingMarkers: null,
      _retryCache: null,
      _transitions: null
    }), e.sibling;
  }
  function qm(t, e, n, a, s) {
    var u = lr();
    return u = u === null ? null : { parent: Kt._currentValue, pool: u }, e.memoizedState = {
      baseLanes: n,
      cachePool: u
    }, t !== null && Ls(e, null), fr(), Zh(e), t !== null && Ra(t, e, a, !0), e.childLanes = s, null;
  }
  function eu(t, e) {
    return e = nu(
      { mode: e.mode, children: e.children },
      t.mode
    ), e.ref = t.ref, t.child = e, e.return = t, e;
  }
  function Gm(t, e, n) {
    return Ba(e, t.child, null, n), t = eu(e, e.pendingProps), t.flags |= 2, ze(e), e.memoizedState = null, t;
  }
  function Rb(t, e, n) {
    var a = e.pendingProps, s = (e.flags & 128) !== 0;
    if (e.flags &= -129, t === null) {
      if (ht) {
        if (a.mode === "hidden")
          return t = eu(e, a), e.lanes = 536870912, t.memoizedState = { baseLanes: 0, cachePool: null }, Cl(null, t);
        if (hr(e), (t = Ut) ? (t = my(
          t,
          Ze
        ), t = t !== null && t.data === "&" ? t : null, t !== null && (e.memoizedState = {
          dehydrated: t,
          treeContext: Kn !== null ? { id: cn, overflow: fn } : null,
          retryLane: 536870912,
          hydrationErrors: null
        }, n = Mh(t), n.return = e, e.child = n, ee = e, Ut = null)) : t = null, t === null) throw kn(e);
        return e.lanes = 536870912, null;
      }
      return eu(e, a);
    }
    var u = t.memoizedState;
    if (u !== null) {
      var f = u.dehydrated;
      if (hr(e), s)
        if (e.flags & 256)
          e.flags &= -257, e = Gm(
            t,
            e,
            n
          );
        else if (e.memoizedState !== null)
          e.child = t.child, e.flags |= 128, e = null;
        else throw Error(o(558));
      else if (kt || Ra(t, e, n, !1), s = (n & t.childLanes) !== 0, kt || s) {
        if (ta.current === null) {
          if (a = zt, a !== null && (f = Od(a, n), f !== 0 && f !== u.retryLane))
            throw u.retryLane = f, Da(t, f), Ce(a, t, f), Vr;
          Tu();
        }
        e = Gm(
          t,
          e,
          n
        );
      } else
        t = u.treeContext, Ut = Ke(f.nextSibling), ee = e, ht = !0, Jn = null, Ze = !1, t !== null && Oh(e, t), e = eu(e, a), e.flags |= 134221824;
      return e;
    }
    return t = wn(t.child, {
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
    return za(e), n = yr(
      t,
      e,
      n,
      a,
      void 0,
      s
    ), a = gr(), t !== null && !kt ? (vr(t, e, s), Un(t, e, s)) : (ht && a && _s(e), e.flags |= 1, Wt(t, e, n, s), e.child);
  }
  function Xm(t, e, n, a, s, u) {
    return za(e), e.updateQueue = null, n = Kh(
      e,
      a,
      n,
      s
    ), Qh(t), a = gr(), t !== null && !kt ? (vr(t, e, u), Un(t, e, u)) : (ht && a && _s(e), e.flags |= 1, Wt(t, e, n, u), e.child);
  }
  function Zm(t, e, n, a, s) {
    if (za(e), e.stateNode === null) {
      var u = di, f = n.contextType;
      typeof f == "object" && f !== null && (u = se(f)), u = new n(a, u), e.memoizedState = u.state !== null && u.state !== void 0 ? u.state : null, u.updater = zr, e.stateNode = u, u._reactInternals = e, u = e.stateNode, u.props = a, u.state = e.memoizedState, u.refs = {}, ur(e), f = n.contextType, u.context = typeof f == "object" && f !== null ? se(f) : di, u.state = e.memoizedState, f = n.getDerivedStateFromProps, typeof f == "function" && (Rr(
        e,
        n,
        f,
        a
      ), u.state = e.memoizedState), typeof n.getDerivedStateFromProps == "function" || typeof u.getSnapshotBeforeUpdate == "function" || typeof u.UNSAFE_componentWillMount != "function" && typeof u.componentWillMount != "function" || (f = u.state, typeof u.componentWillMount == "function" && u.componentWillMount(), typeof u.UNSAFE_componentWillMount == "function" && u.UNSAFE_componentWillMount(), f !== u.state && zr.enqueueReplaceState(u, u.state, null), Tl(e, a, u, s), Sl(), u.state = e.memoizedState), typeof u.componentDidMount == "function" && (e.flags |= 4194308), a = !0;
    } else if (t === null) {
      u = e.stateNode;
      var m = e.memoizedProps, S = Ha(n, m);
      u.props = S;
      var C = u.context, N = n.contextType;
      f = di, typeof N == "object" && N !== null && (f = se(N));
      var _ = n.getDerivedStateFromProps;
      N = typeof _ == "function" || typeof u.getSnapshotBeforeUpdate == "function", m = e.pendingProps !== m, N || typeof u.UNSAFE_componentWillReceiveProps != "function" && typeof u.componentWillReceiveProps != "function" || (m || C !== f) && wm(
        e,
        u,
        a,
        f
      ), Wn = !1;
      var A = e.memoizedState;
      u.state = A, Tl(e, a, u, s), Sl(), C = e.memoizedState, m || A !== C || Wn ? (typeof _ == "function" && (Rr(
        e,
        n,
        _,
        a
      ), C = e.memoizedState), (S = Wn || Nm(
        e,
        n,
        S,
        a,
        A,
        C,
        f
      )) ? (N || typeof u.UNSAFE_componentWillMount != "function" && typeof u.componentWillMount != "function" || (typeof u.componentWillMount == "function" && u.componentWillMount(), typeof u.UNSAFE_componentWillMount == "function" && u.UNSAFE_componentWillMount()), typeof u.componentDidMount == "function" && (e.flags |= 4194308)) : (typeof u.componentDidMount == "function" && (e.flags |= 4194308), e.memoizedProps = a, e.memoizedState = C), u.props = a, u.state = C, u.context = f, a = S) : (typeof u.componentDidMount == "function" && (e.flags |= 4194308), a = !1);
    } else {
      u = e.stateNode, or(t, e), f = e.memoizedProps, N = Ha(n, f), u.props = N, _ = e.pendingProps, A = u.context, C = n.contextType, S = di, typeof C == "object" && C !== null && (S = se(C)), m = n.getDerivedStateFromProps, (C = typeof m == "function" || typeof u.getSnapshotBeforeUpdate == "function") || typeof u.UNSAFE_componentWillReceiveProps != "function" && typeof u.componentWillReceiveProps != "function" || (f !== _ || A !== S) && wm(
        e,
        u,
        a,
        S
      ), Wn = !1, A = e.memoizedState, u.state = A, Tl(e, a, u, s), Sl();
      var O = e.memoizedState;
      f !== _ || A !== O || Wn || t !== null && t.dependencies !== null && Us(t.dependencies) ? (typeof m == "function" && (Rr(
        e,
        n,
        m,
        a
      ), O = e.memoizedState), (N = Wn || Nm(
        e,
        n,
        N,
        a,
        A,
        O,
        S
      ) || t !== null && t.dependencies !== null && Us(t.dependencies)) ? (C || typeof u.UNSAFE_componentWillUpdate != "function" && typeof u.componentWillUpdate != "function" || (typeof u.componentWillUpdate == "function" && u.componentWillUpdate(a, O, S), typeof u.UNSAFE_componentWillUpdate == "function" && u.UNSAFE_componentWillUpdate(
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
    )) : Wt(t, e, n, s), e.memoizedState = u.state, t = e.child) : t = Un(
      t,
      e,
      s
    ), t;
  }
  function Qm(t, e, n, a) {
    return Na(), e.flags |= 256, Wt(t, e, n, a), e.child;
  }
  var Ur = {
    dehydrated: null,
    treeContext: null,
    retryLane: 0,
    hydrationErrors: null
  };
  function Br(t) {
    return { baseLanes: t, cachePool: Vh() };
  }
  function Lr(t, e, n) {
    return t = t !== null ? t.childLanes & ~n : 0, e && (t |= je), t;
  }
  function Km(t, e, n) {
    var a = e.pendingProps, s = !1, u = (e.flags & 128) !== 0, f;
    if ((f = u) || (f = t !== null && t.memoizedState === null ? !1 : (oe.current & 2) !== 0), f && (s = !0, e.flags &= -129), f = (e.flags & 32) !== 0, e.flags &= -33, t === null) {
      if (ht) {
        if (s ? ea(e) : na(), (t = Ut) ? (t = my(
          t,
          Ze
        ), t = t !== null && t.data !== "&" ? t : null, t !== null && (e.memoizedState = {
          dehydrated: t,
          treeContext: Kn !== null ? { id: cn, overflow: fn } : null,
          retryLane: 536870912,
          hydrationErrors: null
        }, n = Mh(t), n.return = e, e.child = n, ee = e, Ut = null)) : t = null, t === null) throw kn(e);
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
      ), u.return = e, a.return = e, u.sibling = a, e.child = u, a = e.child, a.memoizedState = Br(n), a.childLanes = Lr(
        t,
        f,
        n
      ), e.memoizedState = Ur, Cl(null, a)) : (ea(e), Hr(e, u));
    }
    var m = t.memoizedState;
    if (m !== null) {
      var S = m.dehydrated;
      if (S !== null)
        return zb(
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
    return s ? (na(), s = a.fallback, u = e.mode, m = t.child, S = m.sibling, a = wn(m, {
      mode: "hidden",
      children: a.children
    }), a.subtreeFlags = m.subtreeFlags & 1206910976, S !== null ? s = wn(S, s) : (s = Oa(
      s,
      u,
      n,
      null
    ), s.flags |= 2), s.return = e, a.return = e, a.sibling = s, e.child = a, Cl(null, a), a = e.child, s = t.child.memoizedState, s === null ? s = Br(n) : (u = s.cachePool, u !== null ? (m = Kt._currentValue, u = u.parent !== m ? { parent: m, pool: m } : u) : u = Vh(), s = {
      baseLanes: s.baseLanes | n,
      cachePool: u
    }), a.memoizedState = s, a.childLanes = Lr(
      t,
      f,
      n
    ), e.memoizedState = Ur, Cl(t.child, a)) : (ea(e), n = t.child, t = n.sibling, n = wn(n, {
      mode: "visible",
      children: a.children
    }), n.return = e, n.sibling = null, t !== null && (f = e.deletions, f === null ? (e.deletions = [t], e.flags |= 16) : f.push(t)), e.child = n, e.memoizedState = null, n);
  }
  function Hr(t, e) {
    return e = nu(
      { mode: "visible", children: e },
      t.mode
    ), e.return = t, t.child = e;
  }
  function nu(t, e) {
    return t = xe(22, t, null, e), t.lanes = 0, t;
  }
  function au(t, e, n) {
    return Ba(e, t.child, null, n), t = Hr(
      e,
      e.pendingProps.children
    ), t.flags |= 2, e.memoizedState = null, t;
  }
  function zb(t, e, n, a, s, u, f, m) {
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
      ), u.flags |= 2, s.return = e, u.return = e, s.sibling = u, e.child = s, Ba(e, t.child, null, m), s = e.child, s.memoizedState = Br(m), s.childLanes = Lr(
        t,
        a,
        m
      ), e.memoizedState = Ur, Cl(null, s));
    if (ea(e), Bc(u)) {
      if (a = u.nextSibling && u.nextSibling.dataset, a) var S = a.dgst;
      return a = S, a !== "" && (s = Error(o(419)), s.stack = "", s.digest = a, ml({ value: s, source: null, stack: null })), au(
        t,
        e,
        m
      );
    }
    if (kt || Ra(t, e, m, !1), a = (m & t.childLanes) !== 0, kt || a) {
      if (ta.current !== null)
        return au(
          t,
          e,
          m
        );
      if (a = zt, a !== null && (s = Od(
        a,
        m
      ), s !== 0 && s !== f.retryLane))
        throw f.retryLane = s, Da(t, s), Ce(a, t, s), Vr;
      return Uc(u) || Tu(), au(
        t,
        e,
        m
      );
    }
    return Uc(u) ? (e.flags |= 192, e.child = t.child, null) : (t = f.treeContext, Ut = Ke(u.nextSibling), ee = e, ht = !0, Jn = null, Ze = !1, t !== null && Oh(e, t), e = Hr(
      e,
      s.children
    ), e.flags |= 134221824, e);
  }
  function Jm(t, e, n) {
    t.lanes |= e;
    var a = t.alternate;
    a !== null && (a.lanes |= e), js(t.return, e, n);
  }
  function km(t) {
    for (var e = null; t !== null; ) {
      var n = t.alternate;
      n !== null && Zs(n) === null && (e = t), t = t.sibling;
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
    var f = oe.current;
    if (e.flags & 128)
      return xl(e, f), null;
    var m = (f & 2) !== 0;
    if (m ? (f = f & 1 | 2, e.flags |= 128) : f &= 1, xl(e, f), s === "backwards" && t !== null ? (Yr(t), Wt(t, e, a, n), Yr(t)) : Wt(t, e, a, n), a = ht ? hl : 0, !m && t !== null && (t.flags & 128) !== 0)
      t: for (t = e.child; t !== null; ) {
        if (t.tag === 13)
          t.memoizedState !== null && Jm(t, n, e);
        else if (t.tag === 19)
          Jm(t, n, e);
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
        n = km(e.child), n === null ? (s = e.child, e.child = null) : (s = n.sibling, n.sibling = null, Yr(e)), iu(
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
          if (t = s.alternate, t !== null && Zs(t) === null) {
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
        n = km(e.child), n === null ? (s = e.child, e.child = null) : (s = n.sibling, n.sibling = null), iu(
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
  function Pm(t, e, n) {
    var a = e.pendingProps;
    return Pn(e, e.type, a.value), Wt(t, e, a.children, n), e.child;
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
      for (t = e.child, n = wn(t, t.pendingProps), e.child = n, n.return = e; t.sibling !== null; )
        t = t.sibling, n = n.sibling = wn(t, t.pendingProps), n.return = e;
      n.sibling = null;
    }
    return e.child;
  }
  function Gr(t, e) {
    return (t.lanes & e) !== 0 ? !0 : (t = t.dependencies, !!(t !== null && Us(t)));
  }
  function _b(t, e, n) {
    switch (e.tag) {
      case 3:
        rs(e, e.stateNode.containerInfo), Pn(e, Kt, t.memoizedState.cache), Na();
        break;
      case 27:
      case 5:
        po(e);
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
          return e.flags |= 128, hr(e), null;
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
          return a || (n & s) !== 0 ? Km(t, e, n) : (ea(e), t = Un(
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
        if (s = e.memoizedState, s !== null && (s.rendering = null, s.tail = null, s.lastEffect = null), xl(e, oe.current), a) break;
        return null;
      case 22:
        return e.lanes = 0, Ym(
          t,
          e,
          n,
          e.pendingProps
        );
      case 24:
        Pn(e, Kt, t.memoizedState.cache);
    }
    return Un(t, e, n);
  }
  function Fm(t, e, n) {
    if (t !== null)
      if (t.memoizedProps !== e.pendingProps)
        kt = !0;
      else {
        if (!Gr(t, n) && (e.flags & 128) === 0)
          return kt = !1, _b(
            t,
            e,
            n
          );
        kt = (t.flags & 131072) !== 0;
      }
    else
      kt = !1, ht && (e.flags & 1048576) !== 0 && Dh(e, hl, e.index);
    switch (e.lanes = 0, e.tag) {
      case 16:
        t: {
          var a = e.pendingProps;
          if (t = ja(e.elementType), e.type = t, typeof t == "function")
            Po(t) ? (a = Ha(t, a), e.tag = 1, e = Zm(
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
              if (s === Y) {
                e.tag = 11, e = Bm(
                  null,
                  e,
                  t,
                  a,
                  n
                );
                break t;
              } else if (s === at) {
                e.tag = 14, e = Lm(
                  null,
                  e,
                  t,
                  a,
                  n
                );
                break t;
              } else if (s === Ct) {
                e.tag = 10, e.type = t, e = Pm(
                  null,
                  e,
                  n
                );
                break t;
              }
            }
            throw e = Tt(t) || t, Error(o(306, e, ""));
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
        return a = e.type, s = Ha(
          a,
          e.pendingProps
        ), Zm(
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
          if (a = f.cache, Pn(e, Kt, a), a !== u.cache && nr(
            e,
            [Kt],
            n,
            !0
          ), Sl(), a = f.element, u.isDehydrated)
            if (u = {
              element: a,
              isDehydrated: !1,
              cache: f.cache
            }, e.updateQueue.baseState = u, e.memoizedState = u, e.flags & 256) {
              e = Qm(
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
              ), ml(s), e = Qm(
                t,
                e,
                a,
                n
              );
              break t;
            } else
              for (t = e.stateNode.containerInfo, t.nodeType === 9 ? t = t.body : t = t.nodeName === "HTML" ? t.ownerDocument.body : t, Ut = Ke(t.firstChild), ee = e, ht = !0, Jn = null, Ze = !0, n = Yh(
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
            Wt(t, e, a, n);
          }
          e = e.child;
        }
        return e;
      case 26:
        return xi(t, e), t === null ? (n = Ty(
          e.type,
          null,
          e.pendingProps,
          null
        )) ? e.memoizedState = n : ht || (e.stateNode = ty(
          e.type,
          e.pendingProps,
          qn.current,
          e
        )) : e.memoizedState = Ty(
          e.type,
          t.memoizedProps,
          e.pendingProps,
          t.memoizedState
        ), null;
      case 27:
        return po(e), t === null && ht && (a = e.stateNode = gy(
          e.type,
          e.pendingProps,
          qn.current
        ), ee = e, Ze = !0, s = Ut, ca(e.type) ? (Lc = s, Ut = Ke(a.firstChild)) : Ut = s), Wt(
          t,
          e,
          e.pendingProps.children,
          n
        ), xi(t, e), t === null && (e.flags |= 4194304), e.child;
      case 5:
        return t === null && ht && ((s = a = Ut) && (a = DS(
          a,
          e.type,
          e.pendingProps,
          Ze
        ), a !== null ? (e.stateNode = a, ee = e, Ut = Ke(a.firstChild), Ze = !1, s = !0) : s = !1), s || kn(e)), po(e), s = e.type, u = e.pendingProps, f = t !== null ? t.memoizedProps : null, a = u.children, Nc(s, u) ? a = null : f !== null && Nc(s, f) && (e.flags |= 32), e.memoizedState !== null && (s = yr(
          t,
          e,
          xb,
          null,
          null,
          n
        ), Yi._currentValue = s), xi(t, e), Wt(t, e, a, n), e.child;
      case 6:
        return t === null && ht && ((t = n = Ut) && (n = OS(
          n,
          e.pendingProps,
          Ze
        ), n !== null ? (e.stateNode = n, ee = e, Ut = null, t = !0) : t = !1), t || kn(e)), null;
      case 13:
        return Km(t, e, n);
      case 4:
        return rs(
          e,
          e.stateNode.containerInfo
        ), a = e.pendingProps, t === null ? e.child = Ba(
          e,
          null,
          a,
          n
        ) : Wt(t, e, a, n), e.child;
      case 11:
        return Bm(
          t,
          e,
          e.type,
          e.pendingProps,
          n
        );
      case 7:
        return a = e.pendingProps, xi(t, e), Wt(t, e, a, n), e.child;
      case 8:
        return Wt(
          t,
          e,
          e.pendingProps.children,
          n
        ), e.child;
      case 12:
        return Wt(
          t,
          e,
          e.pendingProps.children,
          n
        ), e.child;
      case 10:
        return Pm(t, e, n);
      case 9:
        return s = e.type._context, a = e.pendingProps.children, za(e), s = se(s), a = a(s), e.flags |= 1, Wt(t, e, a, n), e.child;
      case 14:
        return Lm(
          t,
          e,
          e.type,
          e.pendingProps,
          n
        );
      case 15:
        return Hm(
          t,
          e,
          e.type,
          e.pendingProps,
          n
        );
      case 19:
        return qr(t, e, n);
      case 31:
        return Rb(t, e, n);
      case 22:
        return Ym(
          t,
          e,
          n,
          e.pendingProps
        );
      case 24:
        return za(e), a = se(Kt), t === null ? (s = lr(), s === null && (s = zt, u = ar(), s.pooledCache = u, u.refCount++, u !== null && (s.pooledCacheLanes |= n), s = u), e.memoizedState = { parent: a, cache: s }, ur(e), Pn(e, Kt, s)) : ((t.lanes & n) !== 0 && (or(t, e), Tl(e, null, null, n), Sl()), s = t.memoizedState, u = e.memoizedState, s.parent !== a ? (s = { parent: a, cache: a }, e.memoizedState = s, e.lanes === 0 && (e.memoizedState = e.updateQueue.baseState = s), Pn(e, Kt, a)) : (a = u.cache, Pn(e, Kt, a), a !== s.cache && nr(
          e,
          [Kt],
          n,
          !0
        ))), Wt(
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
        }), a = e.pendingProps, a.name != null && a.name !== "auto" ? e.flags |= t === null ? 18882560 : 18874368 : ht && _s(e), t !== null && t.memoizedProps.name !== a.name ? e.flags |= 4194816 : xi(t, e), Wt(t, e, a.children, n), e.child;
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
    if ((u = (t.mode & 32) !== 0) && (u = n === null ? My(e, a) : My(e, a) && (a.src !== n.src || a.srcSet !== n.srcSet)), u) {
      if (t.flags |= 16777216, (s & 335544128) === s)
        if (t.stateNode.complete) t.flags |= 8192;
        else if (Rp()) t.flags |= 8192;
        else
          throw Ua = Ys, sr;
    } else t.flags &= -16777217;
  }
  function Wm(t, e) {
    if (e.type !== "stylesheet" || (e.state.loading & 4) !== 0)
      t.flags &= -16777217;
    else if (t.flags |= 16777216, !Cy(e))
      if (Rp()) t.flags |= 8192;
      else
        throw Ua = Ys, sr;
  }
  function lu(t, e) {
    e !== null && (t.flags |= 4), t.flags & 16384 && (e = t.tag !== 22 ? Md() : 536870912, t.lanes |= e, Di |= e);
  }
  function Dl(t, e) {
    if (!ht)
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
  function Vb(t, e, n) {
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
        return n = e.stateNode, a = null, t !== null && (a = t.memoizedState.cache), e.memoizedState.cache !== a && (e.flags |= 2048), _n(Kt), $a(), n.pendingContext && (n.context = n.pendingContext, n.pendingContext = null), (t === null || t.child === null) && (pi(e) ? Bn(e) : t === null || t.memoizedState.isDehydrated && (e.flags & 256) === 0 || (e.flags |= 1024, tr())), Bt(e), null;
      case 26:
        var s = e.type, u = e.memoizedState;
        return t === null ? (Bn(e), u !== null ? (Bt(e), Wm(e, u)) : (Bt(e), Xr(
          e,
          s,
          null,
          a,
          n
        ))) : u ? u !== t.memoizedState ? (Bn(e), Bt(e), Wm(e, u)) : (Bt(e), e.flags &= -16777217) : (t = t.memoizedProps, t !== a && Bn(e), Bt(e), Xr(
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
          t = on.current, pi(e) ? Nh(e) : (t = gy(s, a, n), e.stateNode = t, Bn(e));
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
          if (u = on.current, pi(e))
            Nh(e);
          else {
            var f = Ll(
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
            u[le] = e, u[Te] = a;
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
            t: switch (ce(u, s, a), s) {
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
          if (t = qn.current, pi(e)) {
            if (t = e.stateNode, n = e.memoizedProps, a = null, s = ee, s !== null)
              switch (s.tag) {
                case 27:
                case 5:
                  a = s.memoizedProps;
              }
            t[le] = e, t = !!(t.nodeValue === n || a !== null && a.suppressHydrationWarning === !0 || Fp(t.nodeValue, n)), t || kn(e, !0);
          } else
            t = Ll(t).createTextNode(
              a
            ), t[le] = e, e.stateNode = t;
        }
        return Bt(e), null;
      case 31:
        if (n = e.memoizedState, t === null || t.memoizedState !== null) {
          if (a = pi(e), n !== null) {
            if (t === null) {
              if (!a) throw Error(o(318));
              if (t = e.memoizedState, t = t !== null ? t.dehydrated : null, !t) throw Error(o(557));
              t[le] = e;
            } else
              Na(), (e.flags & 128) === 0 && (e.memoizedState = null), e.flags |= 4;
            Bt(e), t = !1;
          } else
            n = tr(), t !== null && t.memoizedState !== null && (t.memoizedState.hydrationErrors = n), t = !0;
          if (!t)
            return e.flags & 256 ? (ze(e), e) : (ze(e), null);
          if ((e.flags & 128) !== 0)
            throw Error(o(558));
        }
        return Bt(e), null;
      case 13:
        if (a = e.memoizedState, t === null || t.memoizedState !== null && t.memoizedState.dehydrated !== null) {
          if (s = pi(e), a !== null && a.dehydrated !== null) {
            if (t === null) {
              if (!s) throw Error(o(318));
              if (s = e.memoizedState, s = s !== null ? s.dehydrated : null, !s) throw Error(o(317));
              s[le] = e;
            } else
              Na(), (e.flags & 128) === 0 && (e.memoizedState = null), e.flags |= 4;
            Bt(e), s = !1;
          } else
            s = tr(), t !== null && t.memoizedState !== null && (t.memoizedState.hydrationErrors = s), s = !0;
          if (!s)
            return e.flags & 256 ? (ze(e), e) : (ze(e), null);
        }
        return ze(e), (e.flags & 128) !== 0 ? (e.lanes = n, e) : (n = a !== null, t = t !== null && t.memoizedState !== null, n && (a = e.child, s = null, a.alternate !== null && a.alternate.memoizedState !== null && a.alternate.memoizedState.cachePool !== null && (s = a.alternate.memoizedState.cachePool.pool), u = null, a.memoizedState !== null && a.memoizedState.cachePool !== null && (u = a.memoizedState.cachePool.pool), u !== s && (a.flags |= 2048)), n !== t && n && (e.child.flags |= 8192), lu(e, e.updateQueue), Bt(e), null);
      case 4:
        return $a(), t === null && Ac(e.stateNode.containerInfo), e.flags |= 67108864, Bt(e), null;
      case 10:
        return _n(e.type), Bt(e), null;
      case 19:
        if (mr(e), a = e.memoizedState, a === null) return Bt(e), null;
        if (s = (e.flags & 128) !== 0, u = a.rendering, u === null)
          if (s) Dl(a, !1);
          else {
            if (qt !== 0 || t !== null && (t.flags & 128) !== 0)
              for (t = e.child; t !== null; ) {
                if (u = Zs(t), u !== null) {
                  for (e.flags |= 128, Dl(a, !1), t = u.updateQueue, e.updateQueue = t, lu(e, t), e.subtreeFlags = 0, t = n, n = e.child; n !== null; )
                    Ah(n, t), n = n.sibling;
                  return xl(
                    e,
                    oe.current & 1 | 2
                  ), ht && Rn(e, a.treeForkCount), e.child;
                }
                t = t.sibling;
              }
            a.tail !== null && De() > gu && (e.flags |= 128, s = !0, Dl(a, !1), e.lanes = 4194304);
          }
        else {
          if (!s)
            if (t = Zs(u), t !== null) {
              if (e.flags |= 128, s = !0, t = t.updateQueue, e.updateQueue = t, lu(e, t), Dl(a, !0), a.tail === null && a.tailMode !== "collapsed" && a.tailMode !== "visible" && !u.alternate && !ht)
                return Bt(e), null;
            } else
              2 * De() - a.renderingStartTime > gu && n !== 536870912 && (e.flags |= 128, s = !0, Dl(a, !1), e.lanes = 4194304);
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
          return a.rendering = t, a.tail = t.sibling, a.renderingStartTime = De(), t.sibling = null, u = oe.current, u = s ? u & 1 | 2 : u & 1, a.tailMode === "visible" || a.tailMode === "collapsed" || !n || ht ? xl(e, u) : (n = u, jt(ue, e), jt(oe, n), me === null && (me = e)), ht && Rn(e, a.treeForkCount), t;
        }
        return Bt(e), null;
      case 22:
      case 23:
        return ze(e), dr(), a = e.memoizedState !== null, t !== null ? t.memoizedState !== null !== a && (e.flags |= 8192) : a && (e.flags |= 8192), a ? (n & 536870912) !== 0 && (e.flags & 128) === 0 && (Bt(e), e.subtreeFlags & 6 && (e.flags |= 8192)) : Bt(e), n = e.updateQueue, n !== null && lu(e, n.retryQueue), n = null, t !== null && t.memoizedState !== null && t.memoizedState.cachePool !== null && (n = t.memoizedState.cachePool.pool), a = null, e.memoizedState !== null && e.memoizedState.cachePool !== null && (a = e.memoizedState.cachePool.pool), a !== n && (e.flags |= 2048), t !== null && ie(Va), null;
      case 24:
        return n = null, t !== null && (n = t.memoizedState.cache), e.memoizedState.cache !== n && (e.flags |= 2048), _n(Kt), Bt(e), null;
      case 25:
        return null;
      case 30:
        return e.flags |= 33554432, Bt(e), null;
    }
    throw Error(o(156, e.tag));
  }
  function jb(t, e) {
    switch (Io(e), e.tag) {
      case 1:
        return t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 3:
        return _n(Kt), $a(), t = e.flags, (t & 65536) !== 0 && (t & 128) === 0 ? (e.flags = t & -65537 | 128, e) : null;
      case 26:
      case 27:
      case 5:
        return cs(e), null;
      case 31:
        if (e.memoizedState !== null) {
          if (ze(e), e.alternate === null)
            throw Error(o(340));
          Na();
        }
        return t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 13:
        if (ze(e), t = e.memoizedState, t !== null && t.dehydrated !== null) {
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
        return _n(e.type), null;
      case 22:
      case 23:
        return ze(e), dr(), t !== null && ie(Va), t = e.flags, t & 65536 ? (e.flags = t & -65537 | 128, e) : null;
      case 24:
        return _n(Kt), null;
      case 25:
        return null;
      default:
        return null;
    }
  }
  function Im(t, e) {
    switch (Io(e), e.tag) {
      case 3:
        _n(Kt), $a();
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
        e.memoizedState !== null && ze(e);
        break;
      case 13:
        ze(e);
        break;
      case 19:
        mr(e);
        break;
      case 10:
        _n(e.type);
        break;
      case 22:
      case 23:
        ze(e), dr(), t !== null && ie(Va);
        break;
      case 24:
        _n(Kt);
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
      Nt(e, e.return, m);
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
              var S = n, C = m;
              try {
                C();
              } catch (N) {
                Nt(
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
      Nt(e, e.return, N);
    }
  }
  function $m(t) {
    var e = t.updateQueue;
    if (e !== null) {
      var n = t.stateNode;
      try {
        Gh(e, n);
      } catch (a) {
        Nt(t, t.return, a);
      }
    }
  }
  function tp(t, e, n) {
    n.props = Ha(
      t.type,
      t.memoizedProps
    ), n.state = t.memoizedState;
    try {
      n.componentWillUnmount();
    } catch (a) {
      Nt(t, e, a);
    }
  }
  function dn(t, e) {
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
            (s.ref === null || s.ref.name !== u) && (s.ref = uy(u)), a = s.ref;
            break;
          case 7:
            if (t.stateNode === null) {
              var f = new Be(t);
              y(
                t.child,
                !1,
                MS,
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
      Nt(t, e, m);
    }
  }
  function re(t, e) {
    var n = t.ref, a = t.refCleanup;
    if (n !== null)
      if (typeof a == "function")
        try {
          a();
        } catch (s) {
          Nt(t, e, s);
        } finally {
          t.refCleanup = null, t = t.alternate, t != null && (t.refCleanup = null);
        }
      else if (typeof n == "function")
        try {
          n(null);
        } catch (s) {
          Nt(t, e, s);
        }
      else n.current = null;
  }
  function su(t, e) {
    if ((t.tag === 5 || t.tag === 27 || t.tag === 6) && t.alternate === null && e !== null)
      for (var n = 0; n < e.length; n++)
        hy(
          t.stateNode,
          e[n]
        );
  }
  function ep(t) {
    for (var e = t.return; e !== null && (Qr(e) && hy(t.stateNode, e.stateNode), !Zr(e)); )
      e = e.return;
  }
  function Nl(t) {
    for (var e = t.return; e !== null && (Qr(e) && CS(t.stateNode, e.stateNode), !Zr(e)); )
      e = e.return;
  }
  function Zr(t) {
    return t.tag === 5 || t.tag === 3 || t.tag === 27;
  }
  function Qr(t) {
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
      Nt(t, t.return, s);
    }
  }
  function Jr(t, e, n) {
    try {
      var a = t.stateNode;
      uS(a, t.type, n, e), a[Te] = e;
    } catch (s) {
      Nt(t, t.return, s);
    }
  }
  function np(t) {
    return t.tag === 5 || t.tag === 3 || t.tag === 26 || t.tag === 27 && ca(t.type) || t.tag === 4;
  }
  function kr(t) {
    t: for (; ; ) {
      for (; t.sibling === null; ) {
        if (t.return === null || np(t.return)) return null;
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
      s = t.stateNode, e ? (n.nodeType === 9 ? n.body : n.nodeName === "HTML" ? n.ownerDocument.body : n).insertBefore(s, e) : (e = n.nodeType === 9 ? n.body : n.nodeName === "HTML" ? n.ownerDocument.body : n, e.appendChild(s), n = n._reactRootContainer, n != null || e.onclick !== null || (e.onclick = rn)), su(t, a), xt = !0;
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
      s = t.stateNode, e ? n.insertBefore(s, e) : n.appendChild(s), su(t, a), xt = !0;
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
  function ap(t) {
    var e = t.stateNode, n = t.memoizedProps;
    try {
      for (var a = t.type, s = e.attributes; s.length; )
        e.removeAttributeNode(s[0]);
      ce(e, a, n), e[le] = t, e[Te] = n;
    } catch (u) {
      Nt(t, t.return, u);
    }
  }
  var ou = !1, _e = null;
  function ip(t) {
    (t.tag === 30 || (t.subtreeFlags & 33554432) !== 0) && (ou = !0);
  }
  var hn = null;
  function lp() {
    var t = hn;
    return hn = null, t;
  }
  var Ee = 0;
  function Ei(t, e, n, a, s) {
    return Ee = 0, sp(
      t.child,
      e,
      n,
      a,
      s
    );
  }
  function sp(t, e, n, a, s) {
    for (var u = !1; t !== null; ) {
      if (t.tag === 5) {
        var f = t.stateNode;
        if (a !== null) {
          var m = zc(f);
          a.push(m), m.view && (u = !0);
        } else
          u || zc(f).view && (u = !0);
        ou = !0, ly(
          f,
          Ee === 0 ? e : e + "_" + Ee,
          n
        ), Ee++;
      } else (t.tag !== 22 || t.memoizedState === null) && (t.tag === 30 && s || sp(
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
      t.tag === 5 ? sy(t.stateNode, t.memoizedProps) : (t.tag !== 22 || t.memoizedState === null) && (t.tag === 30 && e || mn(
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
    if (_e !== null && _e.size !== 0) {
      var e = _e;
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
      var e = t.memoizedProps, n = On(e, t.stateNode), a = _e !== null ? _e.get(n) : void 0, s = Nn(
        e.default,
        a !== void 0 ? e.share : e.exit
      );
      s !== "none" && (Ei(t, n, s, null, !1) ? a !== void 0 ? (s = t.stateNode, a.paired = s, s.paired = a, _e.delete(n), Ri(t, e.onShare)) : Ri(t, e.onExit) : mn(t.child, !1)), _e !== null && Wr(t);
    } else if ((t.subtreeFlags & 33554432) !== 0)
      for (t = t.child; t !== null; )
        Ir(t), t = t.sibling;
    else
      _e !== null && Wr(t);
  }
  function up(t) {
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
        (t.subtreeFlags & 33554432) !== 0 && up(t);
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
  function op(t) {
    for (t = t.child; t !== null; )
      t.tag === 30 ? mn(t.child, !1) : (t.subtreeFlags & 33554432) !== 0 && op(t), t = t.sibling;
  }
  function tc(t, e, n, a, s, u, f) {
    for (var m = !1; e !== null; ) {
      if (e.tag === 5) {
        var S = e.stateNode;
        if (u !== null && Ee < u.length) {
          var C = u[Ee], N = zc(S);
          (C.view || N.view) && (m = !0);
          var _;
          if (_ = (t.flags & 4) === 0)
            if (N.clip) _ = !0;
            else {
              _ = C.rect;
              var A = N.rect;
              _ = _.y !== A.y || _.x !== A.x || _.height !== A.height || _.width !== A.width;
            }
          _ && (t.flags |= 4), N.abs ? N = !C.abs : (C = C.rect, N = N.rect, N = C.height !== N.height || C.width !== N.width), N && (t.flags |= 32);
        } else t.flags |= 32;
        (t.flags & 4) !== 0 && ly(
          S,
          Ee === 0 ? n : n + "_" + Ee,
          s
        ), m && (t.flags & 4) !== 0 || (hn === null && (hn = []), hn.push(
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
  function rp(t, e) {
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
        (t.subtreeFlags & 33554432) !== 0 && rp(t);
      t = t.sibling;
    }
  }
  var ne = !1, Dt = !1, pn = !1, ec = !1, cp = typeof WeakSet == "function" ? WeakSet : Set, ae = null, yn = !1, wl = !1, fu = !1, nc = !1;
  function Ub(t, e, n) {
    if (t = t.containerInfo, Dc = qi, t = mh(t), Go(t)) {
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
            var m = 0, S = -1, C = -1, N = 0, _ = 0, A = t, O = null;
            e: for (; ; ) {
              for (var G; A !== a || u !== 0 && A.nodeType !== 3 || (S = m + u), A !== f || s !== 0 && A.nodeType !== 3 || (C = m + s), A.nodeType === 3 && (m += A.nodeValue.length), (G = A.firstChild) !== null; )
                O = A, A = G;
              for (; ; ) {
                if (A === t) break e;
                if (O === a && ++N === u && (S = m), O === f && ++_ === s && (C = m), (G = A.nextSibling) !== null) break;
                A = O, O = A.parentNode;
              }
              A = G;
            }
            a = S === -1 || C === -1 ? null : { start: S, end: C };
          } else a = null;
        }
      a = a || { start: 0, end: 0 };
    } else a = null;
    for (Oc = { focusedElem: t, selectionRange: a }, qi = !1, n = (n & 335544064) === n, ae = e, e = n ? 9270 : 1024; ae !== null; ) {
      if (t = ae, n && (a = t.deletions, a !== null))
        for (u = 0; u < a.length; u++)
          n && Ir(a[u]);
      if (t.alternate === null && (t.flags & 2) !== 0)
        n && ip(t), du(n);
      else {
        if (t.tag === 22) {
          if (a = t.alternate, t.memoizedState !== null) {
            a !== null && a.memoizedState === null && n && Ir(a), du(n);
            continue;
          } else if (a !== null && a.memoizedState !== null) {
            n && ip(t), du(n);
            continue;
          }
        }
        a = t.child, (t.subtreeFlags & e) !== 0 && a !== null ? (a.return = t, ae = a) : (n && up(t), du(n));
      }
    }
    _e = null;
  }
  function du(t) {
    for (; ae !== null; ) {
      var e = ae, n = t, a = e.alternate, s = e.flags;
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
              var f = Ha(
                e.type,
                s
              );
              n = u.getSnapshotBeforeUpdate(
                f,
                a
              ), u.__reactInternalSnapshotBeforeUpdate = n;
            } catch (m) {
              Nt(e, e.return, m);
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
        a.return = e.return, ae = a;
        break;
      }
      ae = e.return;
    }
  }
  function fp(t, e, n) {
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
              Nt(n, n.return, f);
            }
          else {
            var s = Ha(
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
              Nt(
                n,
                n.return,
                f
              );
            }
          }
        a & 64 && $m(n), a & 512 && dn(n, n.return);
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
            Gh(t, e);
          } catch (f) {
            Nt(n, n.return, f);
          }
        }
        break;
      case 27:
        e === null && a & 4 && ap(n);
      case 26:
      case 5:
        gn(t, n), e === null && a & 4 && Kr(n), a & 512 && dn(n, n.return);
        break;
      case 12:
        gn(t, n);
        break;
      case 31:
        gn(t, n), a & 4 && pp(t, n);
        break;
      case 13:
        gn(t, n), a & 4 && yp(t, n), a & 64 && (t = n.memoizedState, t !== null && (t = t.dehydrated, t !== null && (n = kb.bind(
          null,
          n
        ), NS(t, n))));
        break;
      case 22:
        if (a = n.memoizedState !== null || ne, !a) {
          var u = e !== null && e.memoizedState !== null || Dt;
          e = ne, s = Dt, ne = a, (Dt = u) && !s ? (a = 2, (n.subtreeFlags & 8772) !== 0 && (a |= 1), tn(
            t,
            n,
            a
          )) : gn(t, n), ne = e, Dt = s;
        }
        break;
      case 30:
        gn(t, n), a & 512 && dn(n, n.return);
        break;
      case 7:
        a & 512 && dn(n, n.return);
      default:
        gn(t, n);
    }
  }
  function ac(t, e) {
    for (t = t.child; t !== null; )
      dp(t, e), t = t.sibling;
  }
  function dp(t, e) {
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
          Nt(t, t.return, S);
        }
        ic(t, e);
        break;
      case 6:
        try {
          t.stateNode.nodeValue = e ? "" : t.memoizedProps, xt = !0;
        } catch (S) {
          Nt(t, t.return, S);
        }
        break;
      case 18:
        try {
          var m = t.stateNode;
          e ? iy(m, !0) : iy(t.stateNode, !1);
        } catch (S) {
          Nt(t, t.return, S);
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
              dp(n, a);
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
  function hp(t) {
    var e = t.alternate;
    e !== null && (t.alternate = null, hp(e)), t.child = null, t.deletions = null, t.sibling = null, t.tag === 5 && (e = t.stateNode, e !== null && gs(e)), t.stateNode = null, t.return = null, t.dependencies = null, t.memoizedProps = null, t.memoizedState = null, t.pendingProps = null, t.stateNode = null, t.updateQueue = null;
  }
  var Lt = null, Ae = !1;
  function Ie(t, e, n) {
    for (n = n.child; n !== null; )
      mp(t, e, n), n = n.sibling;
  }
  function mp(t, e, n) {
    if (Oe && typeof Oe.onCommitFiberUnmount == "function")
      try {
        Oe.onCommitFiberUnmount($i, n);
      } catch {
      }
    switch (n.tag) {
      case 26:
        Dt || re(n, e), Ie(
          t,
          e,
          n
        ), n.memoizedState ? n.memoizedState.count-- : n.stateNode && !Dt && (n = n.stateNode, n.parentNode.removeChild(n));
        break;
      case 27:
        Dt || re(n, e), Nl(n);
        var a = Lt, s = Ae;
        ca(n.type) && (Lt = n.stateNode, Ae = !1), Ie(
          t,
          e,
          n
        ), vy(
          n.stateNode,
          n.type,
          n.memoizedProps
        ), Lt = a, Ae = s;
        break;
      case 5:
        Dt || re(n, e), Nl(n);
      case 6:
        if (n.tag === 6 && Nl(n), a = Lt, s = Ae, Lt = null, Ie(
          t,
          e,
          n
        ), Lt = a, Ae = s, Lt !== null)
          if (Ae)
            try {
              (Lt.nodeType === 9 ? Lt.body : Lt.nodeName === "HTML" ? Lt.ownerDocument.body : Lt).removeChild(n.stateNode), xt = !0;
            } catch (u) {
              Nt(
                n,
                e,
                u
              );
            }
          else
            try {
              Lt.removeChild(n.stateNode), xt = !0;
            } catch (u) {
              Nt(
                n,
                e,
                u
              );
            }
        break;
      case 18:
        Lt !== null && (Ae ? (t = Lt, ay(
          t.nodeType === 9 ? t.body : t.nodeName === "HTML" ? t.ownerDocument.body : t,
          n.stateNode
        ), Gi(t)) : ay(Lt, n.stateNode));
        break;
      case 4:
        a = Lt, s = Ae, Lt = n.stateNode.containerInfo, Ae = !0, Ie(
          t,
          e,
          n
        ), Lt = a, Ae = s;
        break;
      case 0:
      case 11:
      case 14:
      case 15:
        aa(2, n, e), Dt || aa(4, n, e), Ie(
          t,
          e,
          n
        );
        break;
      case 1:
        Dt || (re(n, e), a = n.stateNode, typeof a.componentWillUnmount == "function" && tp(
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
        Dt = (a = Dt) || n.memoizedState !== null, Ie(
          t,
          e,
          n
        ), Dt = a;
        break;
      case 30:
        re(n, e), Ie(
          t,
          e,
          n
        );
        break;
      case 7:
        Dt || re(n, e), Ie(
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
  function pp(t, e) {
    if (e.memoizedState === null && (t = e.alternate, t !== null && (t = t.memoizedState, t !== null))) {
      t = t.dehydrated;
      try {
        Gi(t);
      } catch (n) {
        Nt(e, e.return, n);
      }
    }
  }
  function yp(t, e) {
    if (e.memoizedState === null && (t = e.alternate, t !== null && (t = t.memoizedState, t !== null && (t = t.dehydrated, t !== null))))
      try {
        Gi(t);
      } catch (n) {
        Nt(e, e.return, n);
      }
  }
  function Bb(t) {
    switch (t.tag) {
      case 31:
      case 13:
      case 19:
        var e = t.stateNode;
        return e === null && (e = t.stateNode = new cp()), e;
      case 22:
        return t = t.stateNode, e = t._retryCache, e === null && (e = t._retryCache = new cp()), e;
      default:
        throw Error(o(435, t.tag));
    }
  }
  function hu(t, e) {
    var n = Bb(t);
    e.forEach(function(a) {
      if (!n.has(a)) {
        n.add(a);
        var s = Pb.bind(null, t, a);
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
                Lt = S.stateNode, Ae = !1;
                break t;
              }
              break;
            case 5:
              Lt = S.stateNode, Ae = !1;
              break t;
            case 3:
            case 4:
              Lt = S.stateNode.containerInfo, Ae = !0;
              break t;
          }
          S = S.return;
        }
        if (Lt === null) throw Error(o(160));
        mp(f, m, u), Lt = null, Ae = !1, f = u.alternate, f !== null && (f.return = null), u.return = null;
      }
    if (e.subtreeFlags & 13886)
      for (e = e.child; e !== null; )
        gp(e, t, n), e = e.sibling;
  }
  var $e = null;
  function gp(t, e, n) {
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
        ge(e, t, n), ve(t), s & 512 && (Dt || a === null || re(a, a.return)), s & 64 && ne && (t = t.updateQueue, t !== null && (e = t.callbacks, e !== null && (n = t.shared.hiddenCallbacks, t.shared.hiddenCallbacks = n === null ? e : n.concat(e))));
        break;
      case 26:
        if (u = $e, ge(e, t, n), ve(t), s & 512 && (Dt || a === null || re(a, a.return)), s & 4)
          if (s = a !== null ? a.memoizedState : null, n = t.memoizedState, a === null)
            if (n === null)
              if (t.stateNode === null)
                if (ne)
                  t.stateNode = ty(
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
                        a = s.getElementsByTagName("title")[0], (!a || a[nl] || a[le] || a.namespaceURI === "http://www.w3.org/2000/svg" || a.hasAttribute("itemprop")) && (a = s.createElement(e), s.head.insertBefore(
                          a,
                          s.querySelector("head > title")
                        )), ce(a, e, n), a[le] = t, te(a), e = a;
                        break t;
                      case "link":
                        if (u = Ay(
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
                        a = s.createElement(e), ce(a, e, n), s.head.appendChild(a);
                        break;
                      case "meta":
                        if (u = Ay(
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
                        a = s.createElement(e), ce(a, e, n), s.head.appendChild(a);
                        break;
                      default:
                        throw Error(o(468, e));
                    }
                    a[le] = t, te(a), e = a;
                  }
                  t.stateNode = e;
                }
              else
                ne || Gc(u, t.type, t.stateNode);
            else
              t.stateNode = Ey(
                u,
                n,
                t.memoizedProps
              );
          else
            s !== n ? (s === null ? (e = a.stateNode, e === null || Dt || e.parentNode.removeChild(e)) : s.count--, n === null ? ne || Gc(u, t.type, t.stateNode) : Ey(u, n, t.memoizedProps)) : n === null && t.stateNode !== null && Jr(
              t,
              t.memoizedProps,
              a.memoizedProps
            );
        break;
      case 27:
        ge(e, t, n), ve(t), s & 512 && (Dt || a === null || re(a, a.return)), a !== null && s & 4 && Jr(
          t,
          t.memoizedProps,
          a.memoizedProps
        );
        break;
      case 5:
        if (u = pn, pn = !1, ge(e, t, n), pn = u, ve(t), s & 512 && (Dt || a === null || re(a, a.return)), t.flags & 32) {
          e = t.stateNode;
          try {
            li(e, ""), xt = !0;
          } catch (N) {
            Nt(t, t.return, N);
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
            n.nodeValue = e, xt = !0;
          } catch (N) {
            Nt(t, t.return, N);
          }
        }
        break;
      case 3:
        if (xt = !1, Ou = null, u = $e, $e = Hl(e.containerInfo), ge(e, t, n), $e = u, ve(t), s & 4 && a !== null && a.memoizedState.isDehydrated)
          try {
            Gi(e.containerInfo);
          } catch (N) {
            Nt(t, t.return, N);
          }
        ec && (ec = !1, vp(t)), xt = !1;
        break;
      case 4:
        s = pn, pn = ne, a = Ld(), u = $e, $e = Hl(
          t.stateNode.containerInfo
        ), ge(e, t, n), ve(t), $e = u, xt && wl && (fu = !0), xt = a, pn = s;
        break;
      case 12:
        ge(e, t, n), ve(t);
        break;
      case 31:
        ge(e, t, n), ve(t), s & 4 && (e = t.updateQueue, e !== null && (t.updateQueue = null, hu(t, e)));
        break;
      case 13:
        ge(e, t, n), ve(t), t.child.flags & 8192 && t.memoizedState !== null != (a !== null && a.memoizedState !== null) && (yu = De()), s & 4 && (e = t.updateQueue, e !== null && (t.updateQueue = null, hu(t, e)));
        break;
      case 22:
        u = t.memoizedState !== null, f = a !== null && a.memoizedState !== null;
        var m = ne, S = Dt, C = pn;
        ne = m || u, pn = C || u, Dt = S || f, ge(e, t, n), Dt = S, pn = C, ne = m, ve(t), s & 8192 && (e = t.stateNode, e._visibility = u ? e._visibility & -2 : e._visibility | 1, !u || a === null || f || ne || Dt || (e = f || Dt, n = ne, a = Dt, ne = u || ne, Dt = e, ia(t, 2), ne = n, Dt = a), !u && pn || ac(t, u)), s & 4 && (e = t.updateQueue, e !== null && (n = e.retryQueue, n !== null && (e.retryQueue = null, hu(t, n))));
        break;
      case 19:
        ge(e, t, n), ve(t), s & 4 && (e = t.updateQueue, e !== null && (t.updateQueue = null, hu(t, e)));
        break;
      case 30:
        s & 512 && (Dt || a === null || re(a, a.return)), s = Ld(), u = wl, f = (n & 335544064) === n, m = t.memoizedProps, wl = f && Nn(
          m.default,
          m.update
        ) !== "none", ge(e, t, n), ve(t), f && a !== null && xt && (t.flags |= 4), wl = u, xt = s;
        break;
      case 21:
        break;
      case 7:
        s & 512 && (Dt || a === null || re(a, a.return)), a && a.stateNode !== null && (a.stateNode._fragmentFiber = t);
      default:
        ge(e, t, n), ve(t);
    }
  }
  function ve(t) {
    var e = t.flags;
    if (e & 2) {
      try {
        for (var n, a = t.return; a !== null; ) {
          if (np(a)) {
            n = a;
            break;
          }
          a = a.return;
        }
        a = null;
        for (var s = t.return; s !== null; ) {
          if (Qr(s)) {
            var u = s.stateNode;
            a === null ? a = [u] : a.push(u);
          }
          if (Zr(s)) break;
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
            var C = n.stateNode;
            n.flags & 32 && (li(C, ""), n.flags &= -33);
            var N = kr(t);
            uu(
              t,
              N,
              C,
              f
            );
            break;
          case 3:
          case 4:
            var _ = n.stateNode.containerInfo, A = kr(t);
            Pr(
              t,
              A,
              _,
              f
            );
            break;
          default:
            throw Error(o(161));
        }
      } catch (O) {
        Nt(t, t.return, O);
      }
      t.flags &= -3;
    }
    e & 4096 && (t.flags &= -4097);
  }
  function vp(t) {
    if (t.subtreeFlags & 1024)
      for (t = t.child; t !== null; ) {
        var e = t;
        vp(e), e.tag === 5 && e.flags & 1024 && (e = e.stateNode, qi = !0, e.reset(), qi = !1), t = t.sibling;
      }
  }
  function Ai(t, e) {
    if (e.subtreeFlags & 9270)
      for (e = e.child; e !== null; )
        bp(e, t), e = e.sibling;
    else rp(e);
  }
  function bp(t, e) {
    var n = t.alternate;
    if (n === null) Fr(t, !1);
    else
      switch (t.tag) {
        case 3:
          if (nc = yn = !1, lp(), Ai(e, t), !yn && !fu) {
            if (t = hn, t !== null)
              for (var a = 0; a < t.length; a += 3) {
                n = t[a];
                var s = t[a + 1];
                sy(n, t[a + 2]), n = n.ownerDocument.documentElement, n !== null && n.animate(
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
          hn = null;
          break;
        case 5:
          Ai(e, t);
          break;
        case 4:
          a = yn, yn = !1, Ai(e, t), yn && (fu = !0), yn = a;
          break;
        case 22:
          t.memoizedState === null && (n.memoizedState !== null ? Fr(t, !1) : Ai(e, t));
          break;
        case 30:
          a = yn, s = lp(), yn = !1, Ai(e, t), yn && (t.flags |= 4);
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
          ), hn = s) : s !== null && (s.push.apply(s, hn), hn = s), yn = (t.flags & 32) !== 0 ? !0 : a;
          break;
        default:
          Ai(e, t);
      }
  }
  function gn(t, e) {
    if (e.subtreeFlags & 8772)
      for (e = e.child; e !== null; )
        fp(t, e.alternate, e), e = e.sibling;
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
          re(n, n.return);
          var s = n.stateNode;
          typeof s.componentWillUnmount == "function" && tp(
            n,
            n.return,
            s
          ), ia(
            n,
            a
          );
          break;
        case 27:
          (a & 2) !== 0 && vy(
            n.stateNode,
            n.type,
            n.memoizedProps
          );
        case 5:
          re(n, n.return), n.tag !== 5 && n.tag !== 27 || Nl(n), ia(
            n,
            a
          );
          break;
        case 6:
          Nl(n);
          break;
        case 26:
          re(n, n.return), s = n.stateNode, n.memoizedState !== null || s === null || Dt || s.parentNode.removeChild(s), ia(
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
          re(n, n.return), ia(
            n,
            a
          );
          break;
        case 7:
          re(n, n.return);
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
              Nt(a, a.return, N);
            }
          if (a = u, s = a.updateQueue, s !== null) {
            var S = a.stateNode;
            try {
              var C = s.shared.hiddenCallbacks;
              if (C !== null)
                for (s.shared.hiddenCallbacks = null, s = 0; s < C.length; s++)
                  qh(C[s], S);
            } catch (N) {
              Nt(a, a.return, N);
            }
          }
          m && f & 64 && $m(u), dn(u, u.return);
          break;
        case 27:
          (n & 2) !== 0 && ap(u);
        case 5:
          u.tag !== 5 && u.tag !== 27 || ep(u), tn(
            s,
            u,
            n
          ), m && a === null && f & 4 && Kr(u), dn(u, u.return);
          break;
        case 6:
          ep(u);
          break;
        case 26:
          S = u.stateNode, u.memoizedState !== null || S === null || ne || Gc(
            Hl(S.ownerDocument),
            u.type,
            S
          ), tn(
            s,
            u,
            n
          ), m && a === null && f & 4 && Kr(u), dn(u, u.return);
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
          ), m && f & 4 && pp(s, u);
          break;
        case 13:
          tn(
            s,
            u,
            n
          ), m && f & 4 && yp(s, u);
          break;
        case 22:
          u.memoizedState === null && tn(
            s,
            u,
            n
          ), dn(u, u.return);
          break;
        case 30:
          tn(
            s,
            u,
            n
          ), dn(u, u.return);
          break;
        case 7:
          dn(u, u.return);
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
    t !== null && t.memoizedState !== null && t.memoizedState.cachePool !== null && (n = t.memoizedState.cachePool.pool), t = null, e.memoizedState !== null && e.memoizedState.cachePool !== null && (t = e.memoizedState.cachePool.pool), t !== n && (t != null && t.refCount++, n != null && pl(n));
  }
  function sc(t, e) {
    t = null, e.alternate !== null && (t = e.alternate.memoizedState.cache), e = e.memoizedState.cache, e !== t && (e.refCount++, t != null && pl(t));
  }
  function Qe(t, e, n, a) {
    var s = (n & 335544064) === n;
    if (e.subtreeFlags & (s ? 10262 : 10256))
      for (e = e.child; e !== null; )
        Sp(
          t,
          e,
          n,
          a
        ), e = e.sibling;
    else s && op(e);
  }
  function Sp(t, e, n, a) {
    var s = (n & 335544064) === n;
    s && e.alternate === null && e.return !== null && e.return.alternate !== null && cu(e);
    var u = e.flags;
    switch (e.tag) {
      case 0:
      case 11:
      case 15:
        Qe(
          t,
          e,
          n,
          a
        ), u & 2048 && Ol(9, e);
        break;
      case 1:
        Qe(
          t,
          e,
          n,
          a
        );
        break;
      case 3:
        Qe(
          t,
          e,
          n,
          a
        ), s && nc && (t = t.containerInfo, t = t.nodeType === 9 ? t.body : t.nodeName === "HTML" ? t.ownerDocument.body : t, t.style.viewTransitionName === "root" && (t.style.viewTransitionName = ""), t = t.ownerDocument.documentElement, t !== null && t.style.viewTransitionName === "none" && (t.style.viewTransitionName = "")), u & 2048 && (u = null, e.alternate !== null && (u = e.alternate.memoizedState.cache), e = e.memoizedState.cache, e !== u && (e.refCount++, u != null && pl(u)));
        break;
      case 12:
        if (u & 2048) {
          Qe(
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
          } catch (C) {
            Nt(e, e.return, C);
          }
        } else
          Qe(
            t,
            e,
            n,
            a
          );
        break;
      case 31:
        Qe(
          t,
          e,
          n,
          a
        );
        break;
      case 13:
        Qe(
          t,
          e,
          n,
          a
        );
        break;
      case 23:
        break;
      case 22:
        f = e.stateNode, m = e.alternate, e.memoizedState !== null ? (s && m !== null && m.memoizedState === null && cu(m), f._visibility & 2 ? Qe(
          t,
          e,
          n,
          a
        ) : Rl(
          t,
          e
        )) : (s && m !== null && m.memoizedState !== null && cu(e), f._visibility & 2 ? Qe(
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
        Qe(
          t,
          e,
          n,
          a
        ), u & 2048 && sc(e.alternate, e);
        break;
      case 30:
        s && (u = e.alternate, u !== null && (mn(u.child, !0), mn(e.child, !0))), Qe(
          t,
          e,
          n,
          a
        );
        break;
      default:
        Qe(
          t,
          e,
          n,
          a
        );
    }
  }
  function Mi(t, e, n, a, s) {
    for (s = s && ((e.subtreeFlags & 10256) !== 0 || !1), e = e.child; e !== null; ) {
      var u = t, f = e, m = n, S = a, C = f.flags;
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
          )), s && C & 2048 && lc(
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
          ), s && C & 2048 && sc(f.alternate, f);
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
        Tp(
          t,
          e,
          n
        ), t = t.sibling;
  }
  function Tp(t, e, n) {
    switch (t.tag) {
      case 26:
        qa(
          t,
          e,
          n
        ), t.flags & Ya && (t.memoizedState !== null ? XS(
          n,
          $e,
          t.memoizedState,
          t.memoizedProps
        ) : (t = t.stateNode, (e & 335544128) === e && Oy(n, t)));
        break;
      case 5:
        qa(
          t,
          e,
          n
        ), t.flags & Ya && (t = t.stateNode, (e & 335544128) === e && Oy(n, t));
        break;
      case 3:
      case 4:
        var a = $e;
        $e = Hl(t.stateNode.containerInfo), qa(
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
          s.paired = null, _e === null && (_e = /* @__PURE__ */ new Map()), _e.set(a, s);
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
  function xp(t) {
    var e = t.alternate;
    if (e !== null && (t = e.child, t !== null)) {
      e.child = null;
      do
        e = t.sibling, t.sibling = null, t = e;
      while (t !== null);
    }
  }
  function zl(t) {
    var e = t.deletions;
    if ((t.flags & 16) !== 0) {
      if (e !== null)
        for (var n = 0; n < e.length; n++) {
          var a = e[n];
          ae = a, Ap(
            a,
            t
          );
        }
      xp(t);
    }
    if (t.subtreeFlags & 10256)
      for (t = t.child; t !== null; )
        Ep(t), t = t.sibling;
  }
  function Ep(t) {
    switch (t.tag) {
      case 0:
      case 11:
      case 15:
        zl(t), t.flags & 2048 && aa(9, t, t.return);
        break;
      case 3:
        zl(t);
        break;
      case 12:
        zl(t);
        break;
      case 22:
        var e = t.stateNode;
        t.memoizedState !== null && e._visibility & 2 && (t.return === null || t.return.tag !== 13) ? (e._visibility &= -3, mu(t)) : zl(t);
        break;
      default:
        zl(t);
    }
  }
  function mu(t) {
    var e = t.deletions;
    if ((t.flags & 16) !== 0) {
      if (e !== null)
        for (var n = 0; n < e.length; n++) {
          var a = e[n];
          ae = a, Ap(
            a,
            t
          );
        }
      xp(t);
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
  function Ap(t, e) {
    for (; ae !== null; ) {
      var n = ae;
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
          pl(n.memoizedState.cache);
      }
      if (a = n.child, a !== null) a.return = n, ae = a;
      else
        t: for (n = t; ae !== null; ) {
          a = ae;
          var s = a.sibling, u = a.return;
          if (hp(a), a === n) {
            ae = null;
            break t;
          }
          if (s !== null) {
            s.return = u, ae = s;
            break t;
          }
          ae = u;
        }
    }
  }
  var Lb = {
    getCacheForType: function(t) {
      var e = se(Kt), n = e.data.get(t);
      return n === void 0 && (n = t(), e.data.set(t, n)), n;
    },
    cacheSignal: function() {
      return se(Kt).controller.signal;
    }
  }, Hb = typeof WeakMap == "function" ? WeakMap : Map, At = 0, zt = null, mt = null, gt = 0, Ot = 0, Ve = null, la = !1, Ci = !1, uc = !1, Ln = 0, qt = 0, sa = 0, Ga = 0, pu = 0, je = 0, Di = 0, _l = null, Me = null, oc = !1, yu = 0, Mp = 0, gu = 1 / 0, vu = null, ua = null, Ht = 0, en = null, Xa = null, vn = 0, rc = 0, cc = null, Cp = null, Oi = null, Ni = null, wi = null, Vl = 0, bu = null;
  function Ue() {
    return (At & 2) !== 0 && gt !== 0 ? gt & -gt : I.T !== null ? Sc() : Nd();
  }
  function Dp() {
    if (je === 0)
      if ((gt & 536870912) === 0 || ht) {
        var t = hs;
        hs <<= 1, (hs & 3932160) === 0 && (hs = 262144), je = t;
      } else je = 536870912;
    return t = ue.current, t !== null && (t.flags |= 32), je;
  }
  function Ri(t, e) {
    if (e != null) {
      var n = t.stateNode, a = n.ref;
      a === null && (a = n.ref = uy(
        On(t.memoizedProps, n)
      )), Ni === null && (Ni = []), Ni.push(e.bind(null, a));
    }
  }
  function Ce(t, e, n) {
    (t === zt && (Ot === 2 || Ot === 9) || t.cancelPendingCommit !== null) && (zi(t, 0), oa(
      t,
      gt,
      je,
      !1
    )), el(t, n), ((At & 2) === 0 || t !== zt) && (t === zt && ((At & 2) === 0 && (Ga |= n), qt === 4 && oa(
      t,
      gt,
      je,
      !1
    )), bn(t));
  }
  function Op(t, e, n) {
    if ((At & 6) !== 0) throw Error(o(327));
    var a = !n && (e & 127) === 0 && (e & t.expiredLanes) === 0 || tl(t, e), s = a ? Gb(t, e) : dc(t, e, !0), u = a;
    do {
      if (s === 0) {
        Ci && !a && oa(t, e, 0, !1);
        break;
      } else {
        if (n = t.current.alternate, u && !Yb(n)) {
          s = dc(t, e, !1), u = !1;
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
              s = _l;
              var S = m.current.memoizedState.isDehydrated;
              if (S && (zi(m, f).flags |= 256), f = dc(
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
          zi(t, 0), oa(t, e, 0, !0);
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
          if ((e & 62914560) === e && (s = yu + 300 - De(), 10 < s)) {
            if (oa(
              a,
              e,
              je,
              !la
            ), ps(a, 0, !0) !== 0) break t;
            vn = e, a.timeoutHandle = Rc(
              Np.bind(
                null,
                a,
                n,
                Me,
                vu,
                oc,
                e,
                je,
                Ga,
                Di,
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
          Np(
            a,
            n,
            Me,
            vu,
            oc,
            e,
            je,
            Ga,
            Di,
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
  function Np(t, e, n, a, s, u, f, m, S, C, N, _, A, O) {
    t.timeoutHandle = -1;
    var G = e.subtreeFlags, P = (u & 335544064) === u;
    if (_ = null, (P || G & 8192 || (G & 16785408) === 16785408) && (_ = {
      stylesheets: null,
      count: 0,
      imgCount: 0,
      imgBytes: 0,
      suspenseyImages: [],
      waitingForImages: !0,
      waitingForViewTransition: !1,
      unsuspend: rn
    }, _e = null, Tp(
      e,
      u,
      _
    ), P && (G = _, P = t.containerInfo, P = (P.nodeType === 9 ? P : P.ownerDocument).__reactViewTransition, P != null && (G.count++, G.waitingForViewTransition = !0, G = Gl.bind(G), P.finished.then(G, G))), G = (u & 62914560) === u ? yu - De() : (u & 4194048) === u ? Mp - De() : 0, G = ZS(
      _,
      G
    ), G !== null)) {
      vn = u, t.cancelPendingCommit = G(
        Bp.bind(
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
          C,
          N,
          _,
          null,
          A,
          O
        )
      ), oa(t, u, f, !C);
      return;
    }
    Bp(
      t,
      e,
      u,
      n,
      a,
      s,
      f,
      m,
      S,
      C,
      N,
      _
    );
  }
  function Yb(t) {
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
    e = Ad(t, e), e &= ~pu, e &= ~Ga, t.suspendedLanes |= e, t.pingedLanes &= ~e, a && (t.warmLanes |= e), a = t.expirationTimes;
    for (var s = e; 0 < s; ) {
      var u = 31 - Ne(s), f = 1 << u;
      a[u] = -1, s &= ~f;
    }
    n !== 0 && Cd(t, n, e);
  }
  function Su() {
    return (At & 6) === 0 ? (jl(0), !1) : !0;
  }
  function fc() {
    if (mt !== null) {
      if (Ot === 0)
        var t = mt.return;
      else
        t = mt, zn = wa = null, br(t), vi = null, vl = 0, t = mt;
      for (; t !== null; )
        Im(t.alternate, t), t = t.return;
      mt = null;
    }
  }
  function zi(t, e) {
    var n = t.timeoutHandle;
    return n !== -1 && (t.timeoutHandle = -1, cS(n)), n = t.cancelPendingCommit, n !== null && (t.cancelPendingCommit = null, n()), vn = 0, fc(), zt = t, mt = n = wn(t.current, null), gt = e, Ot = 0, Ve = null, la = !1, Ci = tl(t, e), uc = !1, Di = je = pu = Ga = sa = qt = 0, Me = _l = null, oc = !1, Ln = Ad(t, e), Os(), n;
  }
  function wp(t, e) {
    rt = null, I.H = $s, e === gi || e === Hs ? (e = Bh(), Ot = 3) : e === sr ? (e = Bh(), Ot = 4) : Ot = e === Vr ? 8 : e !== null && typeof e == "object" && typeof e.then == "function" ? 6 : 1, Ve = e, mt === null && (qt = 1, tu(
      t,
      qe(e, t.current)
    ));
  }
  function Rp() {
    var t = ue.current;
    return t === null ? !0 : (gt & 4194048) === gt ? me === null : (gt & 62914560) === gt || (gt & 536870912) !== 0 ? t === me : !1;
  }
  function zp() {
    var t = I.H;
    return I.H = $s, t === null ? $s : t;
  }
  function _p() {
    var t = I.A;
    return I.A = Lb, t;
  }
  function Tu() {
    qt = 4, la || (gt & 4194048) !== gt && ue.current !== null || (Ci = !0), (sa & 134217727) === 0 && (Ga & 134217727) === 0 || zt === null || oa(
      zt,
      gt,
      je,
      !1
    );
  }
  function dc(t, e, n) {
    var a = At;
    At |= 2;
    var s = zp(), u = _p();
    (zt !== t || gt !== e) && (vu = null, zi(t, e)), e = !1;
    var f = qt;
    t: do
      try {
        if (Ot !== 0 && mt !== null) {
          var m = mt, S = Ve;
          switch (Ot) {
            case 8:
              fc(), f = 6;
              break t;
            case 3:
            case 2:
            case 9:
            case 6:
              ue.current === null && (e = !0);
              var C = Ot;
              if (Ot = 0, Ve = null, _i(t, m, S, C), n && Ci) {
                f = 0;
                break t;
              }
              break;
            default:
              C = Ot, Ot = 0, Ve = null, _i(t, m, S, C);
          }
        }
        qb(), f = qt;
        break;
      } catch (N) {
        wp(t, N);
      }
    while (!0);
    return e && t.shellSuspendCounter++, zn = wa = null, At = a, I.H = s, I.A = u, mt === null && (zt = null, gt = 0, Os()), f;
  }
  function qb() {
    for (; mt !== null; ) Vp(mt);
  }
  function Gb(t, e) {
    var n = At;
    At |= 2;
    var a = zp(), s = _p();
    zt !== t || gt !== e ? (vu = null, gu = De() + 500, zi(t, e)) : Ci = tl(
      t,
      e
    );
    t: do
      try {
        if (Ot !== 0 && mt !== null) {
          e = mt;
          var u = Ve;
          e: switch (Ot) {
            case 1:
              Ot = 0, Ve = null, _i(t, e, u, 1);
              break;
            case 2:
            case 9:
              if (jh(u)) {
                Ot = 0, Ve = null, jp(e);
                break;
              }
              e = function() {
                Ot !== 2 && Ot !== 9 || zt !== t || (Ot = 7), bn(t);
              }, u.then(e, e);
              break t;
            case 3:
              Ot = 7;
              break t;
            case 4:
              Ot = 5;
              break t;
            case 7:
              jh(u) ? (Ot = 0, Ve = null, jp(e)) : (Ot = 0, Ve = null, _i(t, e, u, 7));
              break;
            case 5:
              var f = null;
              switch (mt.tag) {
                case 26:
                  f = mt.memoizedState;
                case 5:
                case 27:
                  var m = mt;
                  if (f ? Cy(f) : m.stateNode.complete) {
                    Ot = 0, Ve = null;
                    var S = m.sibling;
                    if (S !== null) mt = S;
                    else {
                      var C = m.return;
                      C !== null ? (mt = C, xu(C)) : mt = null;
                    }
                    break e;
                  }
              }
              Ot = 0, Ve = null, _i(t, e, u, 5);
              break;
            case 6:
              Ot = 0, Ve = null, _i(t, e, u, 6);
              break;
            case 8:
              fc(), qt = 6;
              break t;
            default:
              throw Error(o(462));
          }
        }
        Xb();
        break;
      } catch (N) {
        wp(t, N);
      }
    while (!0);
    return zn = wa = null, I.H = a, I.A = s, At = n, mt !== null ? 0 : (zt = null, gt = 0, Os(), qt);
  }
  function Xb() {
    for (; mt !== null && !s1(); )
      Vp(mt);
  }
  function Vp(t) {
    var e = Fm(t.alternate, t, Ln);
    t.memoizedProps = t.pendingProps, e === null ? xu(t) : mt = e;
  }
  function jp(t) {
    var e = t, n = e.alternate;
    switch (e.tag) {
      case 15:
      case 0:
        e = Xm(
          n,
          e,
          e.pendingProps,
          e.type,
          void 0,
          gt
        );
        break;
      case 11:
        e = Xm(
          n,
          e,
          e.pendingProps,
          e.type.render,
          e.ref,
          gt
        );
        break;
      case 5:
        br(e);
        var a = e;
        a === ee && (ht ? (Vs(a), a.tag === 5 && a.stateNode != null && (Ut = a.stateNode)) : (Vs(a), ht = !0));
      default:
        Im(n, e), e = mt = Ah(e, Ln), e = Fm(n, e, Ln);
    }
    t.memoizedProps = t.pendingProps, e === null ? xu(t) : mt = e;
  }
  function _i(t, e, n, a) {
    zn = wa = null, br(e), vi = null, vl = 0;
    var s = e.return;
    try {
      if (wb(
        t,
        s,
        e,
        n,
        gt
      )) {
        qt = 1, tu(
          t,
          qe(n, t.current)
        ), mt = null;
        return;
      }
    } catch (u) {
      if (s !== null) throw mt = s, u;
      qt = 1, tu(
        t,
        qe(n, t.current)
      ), mt = null;
      return;
    }
    e.flags & 32768 ? (ht || a === 1 ? t = !0 : Ci || (gt & 536870912) !== 0 ? t = !1 : (la = t = !0, (a === 2 || a === 9 || a === 3 || a === 6) && (a = ue.current, a !== null && a.tag === 13 && (a.flags |= 16384))), Up(e, t)) : xu(e);
  }
  function xu(t) {
    var e = t;
    do {
      if ((e.flags & 32768) !== 0) {
        Up(
          e,
          la
        );
        return;
      }
      t = e.return;
      var n = Vb(
        e.alternate,
        e,
        Ln
      );
      if (n !== null) {
        mt = n;
        return;
      }
      if (e = e.sibling, e !== null) {
        mt = e;
        return;
      }
      mt = e = t;
    } while (e !== null);
    qt === 0 && (qt = 5);
  }
  function Up(t, e) {
    do {
      var n = jb(t.alternate, t);
      if (n !== null) {
        n.flags &= 32767, mt = n;
        return;
      }
      if (n = t.return, n !== null && (n.flags |= 32768, n.subtreeFlags = 0, n.deletions = null), !e && (t = t.sibling, t !== null)) {
        mt = t;
        return;
      }
      mt = t = n;
    } while (t !== null);
    qt = 6, mt = null;
  }
  function Bp(t, e, n, a, s, u, f, m, S, C, N, _) {
    t.cancelPendingCommit = null;
    do
      Eu();
    while (Ht !== 0);
    if ((At & 6) !== 0) throw Error(o(327));
    if (e !== null) {
      if (e === t.current) throw Error(o(177));
      t === zt && (mt = zt = null, gt = 0), Xa = e, en = t, vn = n, cc = s, Cp = a, Zb(
        t,
        e,
        n,
        f,
        m,
        S,
        _
      );
    }
  }
  function Zb(t, e, n, a, s, u, f) {
    var m = e.lanes | e.childLanes;
    if (rc = m, m |= Jo, y1(
      t,
      n,
      m,
      a,
      s,
      u
    ), Ni = null, (n & 335544064) === n ? (wi = vb(t), a = 10262) : (wi = null, a = 10256), (e.subtreeFlags & a) !== 0 || (e.flags & a) !== 0 ? (t.callbackNode = null, t.callbackPriority = 0, Fb(fs, function() {
      return yc(), null;
    })) : (t.callbackNode = null, t.callbackPriority = 0), ou = !1, a = (e.flags & 13878) !== 0, (e.subtreeFlags & 13878) !== 0 || a) {
      a = I.T, I.T = null, s = st.p, st.p = 2, u = At, At |= 4;
      try {
        Ub(t, e, n);
      } finally {
        At = u, st.p = s, I.T = a;
      }
    }
    Ht = 1, ou ? Oi = yS(
      f,
      t.containerInfo,
      wi,
      hc,
      mc,
      Kb,
      pc,
      yc,
      Qb
    ) : (hc(), mc(), pc());
  }
  function Qb(t) {
    if (Ht !== 0) {
      var e = en.onRecoverableError;
      e(t, { componentStack: null });
    }
  }
  function Kb() {
    Ht === 3 && (Ht = 0, bp(Xa, en), Ht = 4);
  }
  function hc() {
    if (Ht === 1) {
      Ht = 0;
      var t = en, e = Xa, n = vn, a = (e.flags & 13878) !== 0;
      if ((e.subtreeFlags & 13878) !== 0 || a) {
        a = I.T, I.T = null;
        var s = st.p;
        st.p = 2;
        var u = At;
        At |= 4;
        try {
          wl = fu = !1, gp(e, t, n), n = Oc;
          var f = mh(t.containerInfo), m = n.focusedElem, S = n.selectionRange;
          if (f !== m && m && m.ownerDocument && hh(
            m.ownerDocument.documentElement,
            m
          )) {
            if (S !== null && Go(m)) {
              var C = S.start, N = S.end;
              if (N === void 0 && (N = C), "selectionStart" in m)
                m.selectionStart = C, m.selectionEnd = Math.min(
                  N,
                  m.value.length
                );
              else {
                var _ = m.ownerDocument || document, A = _ && _.defaultView || window;
                if (A.getSelection) {
                  var O = A.getSelection(), G = m.textContent.length, P = Math.min(S.start, G), ct = S.end === void 0 ? P : Math.min(S.end, G);
                  !O.extend && P > ct && (f = ct, ct = P, P = f);
                  var M = dh(
                    m,
                    P
                  ), x = dh(
                    m,
                    ct
                  );
                  if (M && x && (O.rangeCount !== 1 || O.anchorNode !== M.node || O.anchorOffset !== M.offset || O.focusNode !== x.node || O.focusOffset !== x.offset)) {
                    var D = _.createRange();
                    D.setStart(M.node, M.offset), O.removeAllRanges(), P > ct ? (O.addRange(D), O.extend(x.node, x.offset)) : (D.setEnd(x.node, x.offset), O.addRange(D));
                  }
                }
              }
            }
            for (_ = [], O = m; O = O.parentNode; )
              O.nodeType === 1 && _.push({
                element: O,
                left: O.scrollLeft,
                top: O.scrollTop
              });
            for (typeof m.focus == "function" && m.focus(), m = 0; m < _.length; m++) {
              var z = _[m];
              z.element.scrollLeft = z.left, z.element.scrollTop = z.top;
            }
          }
          qi = !!Dc, Oc = Dc = null;
        } finally {
          At = u, st.p = s, I.T = a;
        }
      }
      t.current = e, Ht = 2;
    }
  }
  function mc() {
    if (Ht === 2) {
      Ht = 0;
      var t = en, e = Xa, n = (e.flags & 8772) !== 0;
      if ((e.subtreeFlags & 8772) !== 0 || n) {
        n = I.T, I.T = null;
        var a = st.p;
        st.p = 2;
        var s = At;
        At |= 4;
        try {
          fp(t, e.alternate, e);
        } finally {
          At = s, st.p = a, I.T = n;
        }
      }
      Ht = 3;
    }
  }
  function pc() {
    if (Ht === 4 || Ht === 3) {
      Ht = 0;
      var t = Oi;
      Oi = null, u1();
      var e = en, n = Xa, a = vn, s = Cp, u = (a & 335544064) === a ? 10262 : 10256;
      if ((n.subtreeFlags & u) !== 0 || (n.flags & u) !== 0 ? Ht = 5 : (Ht = 0, Xa = en = null, Lp(e, e.pendingLanes)), u = e.pendingLanes, u === 0 && (ua = null), Ao(a), n = n.stateNode, Oe && typeof Oe.onCommitFiberRoot == "function")
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
        n = I.T, u = st.p, st.p = 2, I.T = null;
        try {
          for (var f = e.onRecoverableError, m = 0; m < s.length; m++) {
            var S = s[m];
            f(S.value, {
              componentStack: S.stack
            });
          }
        } finally {
          I.T = n, st.p = u;
        }
      }
      if (s = Ni, f = wi, wi = null, s !== null && (Ni = null, f === null && (f = []), t !== null))
        for (S = 0; S < s.length; S++)
          n = (0, s[S])(
            f
          ), n !== void 0 && t.finished.finally(n);
      (vn & 3) !== 0 && Eu(), bn(e), u = e.pendingLanes, (a & 261930) !== 0 && (u & 42) !== 0 ? e === bu ? Vl++ : (Vl = 0, bu = e) : (Vl = 0, bu = null), jl(0);
    }
  }
  function Lp(t, e) {
    (t.pooledCacheLanes &= e) === 0 && (e = t.pooledCache, e != null && (t.pooledCache = null, pl(e)));
  }
  function Eu() {
    return Oi !== null && (Oi.skipTransition(), Oi = null), hc(), mc(), pc(), yc();
  }
  function yc() {
    if (Ht !== 5) return !1;
    var t = en, e = rc;
    rc = 0;
    var n = Ao(vn), a = I.T, s = st.p;
    try {
      st.p = 32 > n ? 32 : n, I.T = null, n = cc, cc = null;
      var u = en, f = vn;
      if (Ht = 0, Xa = en = null, vn = 0, (At & 6) !== 0) throw Error(o(331));
      var m = At;
      if (At |= 4, Ep(u.current), Sp(
        u,
        u.current,
        f,
        n
      ), At = m, jl(0, !1), Oe && typeof Oe.onPostCommitFiberRoot == "function")
        try {
          Oe.onPostCommitFiberRoot($i, u);
        } catch {
        }
      return !0;
    } finally {
      st.p = s, I.T = a, Lp(t, e);
    }
  }
  function Hp(t, e, n) {
    e = qe(n, e), e = _r(t.stateNode, e, 2), t = $n(t, e, 2), t !== null && (el(t, 2), bn(t));
  }
  function Nt(t, e, n) {
    if (t.tag === 3)
      Hp(t, t, n);
    else
      for (; e !== null; ) {
        if (e.tag === 3) {
          Hp(
            e,
            t,
            n
          );
          break;
        } else if (e.tag === 1) {
          var a = e.stateNode;
          if (typeof e.type.getDerivedStateFromError == "function" || typeof a.componentDidCatch == "function" && (ua === null || !ua.has(a))) {
            t = qe(n, t), n = jm(2), a = $n(e, n, 2), a !== null && (Um(
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
      a = t.pingCache = new Hb();
      var s = /* @__PURE__ */ new Set();
      a.set(e, s);
    } else
      s = a.get(e), s === void 0 && (s = /* @__PURE__ */ new Set(), a.set(e, s));
    s.has(n) || (uc = !0, s.add(n), t = Jb.bind(null, t, e, n), e.then(t, t));
  }
  function Jb(t, e, n) {
    var a = t.pingCache;
    a !== null && a.delete(e), t.pingedLanes |= t.suspendedLanes & n, t.warmLanes &= ~n, zt === t && (gt & n) === n && ((qt === 4 || qt === 3 && (gt & 62914560) === gt && 300 > De() - yu) && (At & 2) === 0 ? zi(t, 0) : pu |= n, Di === gt && (Di = 0)), bn(t);
  }
  function Yp(t, e) {
    e === 0 && (e = Md()), t = Da(t, e), t !== null && (el(t, e), bn(t));
  }
  function kb(t) {
    var e = t.memoizedState, n = 0;
    e !== null && (n = e.retryLane), Yp(t, n);
  }
  function Pb(t, e) {
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
    a !== null && a.delete(e), Yp(t, n);
  }
  function Fb(t, e) {
    return So(t, e);
  }
  var Vi = null, ji = null, vc = !1, Au = !1, bc = !1, ra = 0;
  function bn(t) {
    t !== ji && t.next === null && (ji === null ? Vi = ji = t : ji = ji.next = t), Au = !0, vc || (vc = !0, Ib());
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
            u !== 0 && (n = !0, Zp(a, u));
          } else
            u = gt, u = ps(
              a,
              a === zt ? u : 0,
              a.cancelPendingCommit !== null || a.timeoutHandle !== -1
            ), (u & 3) === 0 || tl(a, u) || (n = !0, Zp(a, u));
          a = a.next;
        }
      while (n);
      bc = !1;
    }
  }
  function Wb() {
    qp();
  }
  function qp() {
    Au = vc = !1;
    var t = 0;
    ra !== 0 && rS() && (t = ra);
    for (var e = De(), n = null, a = Vi; a !== null; ) {
      var s = a.next, u = Gp(a, e);
      u === 0 ? (a.next = null, n === null ? Vi = s : n.next = s, s === null && (ji = n)) : (n = a, (t !== 0 || (u & 3) !== 0) && (Au = !0)), a = s;
    }
    Ht !== 0 && Ht !== 5 || jl(t), ra !== 0 && (ra = 0);
  }
  function Gp(t, e) {
    for (var n = t.suspendedLanes, a = t.pingedLanes, s = t.expirationTimes, u = t.pendingLanes & -62914561; 0 < u; ) {
      var f = 31 - Ne(u), m = 1 << f, S = s[f];
      S === -1 ? ((m & n) === 0 || (m & a) !== 0) && (s[f] = p1(m, e)) : S <= e && (t.expiredLanes |= m), u &= ~m;
    }
    if (e = zt, n = gt, n = ps(
      t,
      t === e ? n : 0,
      t.cancelPendingCommit !== null || t.timeoutHandle !== -1
    ), a = t.callbackNode, n === 0 || t === e && (Ot === 2 || Ot === 9) || t.cancelPendingCommit !== null)
      return a !== null && a !== null && To(a), t.callbackNode = null, t.callbackPriority = 0;
    if ((n & 3) === 0 || tl(t, n)) {
      if (e = n & -n, e === t.callbackPriority) return e;
      switch (a !== null && To(a), Ao(n)) {
        case 2:
        case 8:
          n = xd;
          break;
        case 32:
          n = fs;
          break;
        case 268435456:
          n = Ed;
          break;
        default:
          n = fs;
      }
      return a = Xp.bind(null, t), n = So(n, a), t.callbackPriority = e, t.callbackNode = n, e;
    }
    return a !== null && a !== null && To(a), t.callbackPriority = 2, t.callbackNode = null, 2;
  }
  function Xp(t, e) {
    if (Ht !== 0 && Ht !== 5)
      return t.callbackNode = null, t.callbackPriority = 0, null;
    var n = t.callbackNode;
    if (Eu() && t.callbackNode !== n)
      return null;
    var a = gt;
    return a = ps(
      t,
      t === zt ? a : 0,
      t.cancelPendingCommit !== null || t.timeoutHandle !== -1
    ), a === 0 ? null : (Op(t, a, e), Gp(t, De()), t.callbackNode != null && t.callbackNode === n ? Xp.bind(null, t) : null);
  }
  function Zp(t, e) {
    if (Eu()) return null;
    Op(t, e, !0);
  }
  function Ib() {
    fS(function() {
      (At & 6) !== 0 ? So(
        Td,
        Wb
      ) : qp();
    });
  }
  function Sc() {
    if (ra === 0) {
      var t = _a;
      t === 0 && (t = ds, ds <<= 1, (ds & 261888) === 0 && (ds = 256)), ra = t;
    }
    return ra;
  }
  function Qp(t) {
    return t == null || typeof t == "symbol" || typeof t == "boolean" ? null : typeof t == "function" ? t : Ss(t);
  }
  function $b(t, e, n, a, s) {
    if (e === "submit" && n && n.stateNode === s) {
      var u = Qp(
        (s[Te] || null).action
      ), f = a.submitter;
      f && (e = (e = f[Te] || null) ? Qp(e.formAction) : f.getAttribute("formAction"), e !== null && (u = e, f = null));
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
    var xc = Ko[Tc], tS = xc.toLowerCase(), eS = xc[0].toUpperCase() + xc.slice(1);
    We(
      tS,
      "on" + eS
    );
  }
  We(gh, "onAnimationEnd"), We(vh, "onAnimationIteration"), We(bh, "onAnimationStart"), We("dblclick", "onDoubleClick"), We("focusin", "onFocus"), We("focusout", "onBlur"), We(cb, "onTransitionRun"), We(fb, "onTransitionStart"), We(db, "onTransitionCancel"), We(Sh, "onTransitionEnd"), ai("onMouseEnter", ["mouseout", "mouseover"]), ai("onMouseLeave", ["mouseout", "mouseover"]), ai("onPointerEnter", ["pointerout", "pointerover"]), ai("onPointerLeave", ["pointerout", "pointerover"]), Aa(
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
  ), nS = new Set(
    "beforetoggle cancel close invalid load scroll scrollend toggle".split(" ").concat(Ul)
  );
  function Kp(t, e) {
    e = (e & 4) !== 0;
    for (var n = 0; n < t.length; n++) {
      var a = t[n], s = a.event;
      a = a.listeners;
      t: {
        var u = void 0;
        if (e)
          for (var f = a.length - 1; 0 <= f; f--) {
            var m = a[f], S = m.instance, C = m.currentTarget;
            if (m = m.listener, S !== u && s.isPropagationStopped())
              break t;
            u = m, s.currentTarget = C;
            try {
              u(s);
            } catch (N) {
              Ds(N);
            }
            s.currentTarget = null, u = S;
          }
        else
          for (f = 0; f < a.length; f++) {
            if (m = a[f], S = m.instance, C = m.currentTarget, m = m.listener, S !== u && s.isPropagationStopped())
              break t;
            u = m, s.currentTarget = C;
            try {
              u(s);
            } catch (N) {
              Ds(N);
            }
            s.currentTarget = null, u = S;
          }
      }
    }
  }
  function pt(t, e) {
    var n = e[Rd];
    n === void 0 && (n = e[Rd] = /* @__PURE__ */ new Set());
    var a = t + "__bubble";
    n.has(a) || (Jp(e, t, 2, !1), n.add(a));
  }
  function Ec(t, e, n) {
    var a = 0;
    e && (a |= 4), Jp(
      n,
      t,
      a,
      e
    );
  }
  var Mu = "_reactListening" + Math.random().toString(36).slice(2);
  function Ac(t) {
    if (!t[Mu]) {
      t[Mu] = !0, Vd.forEach(function(n) {
        n !== "selectionchange" && (nS.has(n) || Ec(n, !1, t), Ec(n, !0, t));
      });
      var e = t.nodeType === 9 ? t : t.ownerDocument;
      e === null || e[Mu] || (e[Mu] = !0, Ec("selectionchange", !1, e));
    }
  }
  function Jp(t, e, n, a) {
    switch (Uy(e)) {
      case 2:
        var s = kS;
        break;
      case 8:
        s = PS;
        break;
      default:
        s = Zc;
    }
    n = s.bind(
      null,
      e,
      n,
      t
    ), s = void 0, !zo || e !== "touchstart" && e !== "touchmove" && e !== "wheel" || (s = !0), a ? s !== void 0 ? t.addEventListener(e, n, {
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
    Jd(function() {
      var C = u, N = wo(n), _ = [];
      t: {
        var A = Th.get(t);
        if (A !== void 0) {
          var O = As, G = t;
          switch (t) {
            case "keypress":
              if (xs(n) === 0) break t;
            case "keydown":
            case "keyup":
              O = Y1;
              break;
            case "focusin":
              G = "focus", O = Uo;
              break;
            case "focusout":
              G = "blur", O = Uo;
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
              O = Fd;
              break;
            case "drag":
            case "dragend":
            case "dragenter":
            case "dragexit":
            case "dragleave":
            case "dragover":
            case "dragstart":
            case "drop":
              O = O1;
              break;
            case "touchcancel":
            case "touchend":
            case "touchmove":
            case "touchstart":
              O = Q1;
              break;
            case gh:
            case vh:
            case bh:
              O = R1;
              break;
            case Sh:
              O = J1;
              break;
            case "scroll":
            case "scrollend":
              O = C1;
              break;
            case "wheel":
              O = P1;
              break;
            case "copy":
            case "cut":
            case "paste":
              O = _1;
              break;
            case "gotpointercapture":
            case "lostpointercapture":
            case "pointercancel":
            case "pointerdown":
            case "pointermove":
            case "pointerout":
            case "pointerover":
            case "pointerup":
              O = Id;
              break;
            case "submit":
              O = X1;
              break;
            case "toggle":
            case "beforetoggle":
              O = W1;
          }
          var P = (e & 4) !== 0, ct = !P && (t === "scroll" || t === "scrollend"), M = P ? A !== null ? A + "Capture" : null : A;
          P = [];
          for (var x = C, D; x !== null; ) {
            var z = x;
            if (D = z.stateNode, z = z.tag, z !== 5 && z !== 26 && z !== 27 || D === null || M === null || (z = il(x, M), z != null && P.push(
              Bl(x, z, D)
            )), ct) break;
            x = x.return;
          }
          0 < P.length && (A = new O(
            A,
            G,
            null,
            n,
            N
          ), _.push({ event: A, listeners: P }));
        }
      }
      if ((e & 7) === 0) {
        t: {
          if (O = t === "mouseover" || t === "pointerover", A = t === "mouseout" || t === "pointerout", O && n !== No && (G = n.relatedTarget || n.fromElement) && (Ea(G) || G[ti]))
            break t;
          (A || O) && (G = N.window === N ? N : (O = N.ownerDocument) ? O.defaultView || O.parentWindow : window, A ? (O = n.relatedTarget || n.toElement, A = C, O = O ? Ea(O) : null, O !== null && (ct = h(O), P = O.tag, O !== ct || P !== 5 && P !== 27 && P !== 6) && (O = null)) : (A = null, O = C), A !== O && (P = Fd, z = "onMouseLeave", M = "onMouseEnter", x = "mouse", (t === "pointerout" || t === "pointerover") && (P = Id, z = "onPointerLeave", M = "onPointerEnter", x = "pointer"), ct = A == null ? G : al(A), D = O == null ? G : al(O), G = new P(
            z,
            x + "leave",
            A,
            n,
            N
          ), G.target = ct, G.relatedTarget = D, z = null, Ea(N) === C && (P = new P(
            M,
            x + "enter",
            O,
            n,
            N
          ), P.target = D, P.relatedTarget = ct, z = P), ct = z, P = A && O ? dt(
            A,
            O,
            aS
          ) : null, A !== null && kp(
            _,
            G,
            A,
            P,
            !1
          ), O !== null && ct !== null && kp(
            _,
            ct,
            O,
            P,
            !0
          )));
        }
        t: {
          if (A = C ? al(C) : window, O = A.nodeName && A.nodeName.toLowerCase(), O === "select" || O === "input" && A.type === "file")
            var k = sh;
          else if (ih(A))
            if (uh)
              k = ub;
            else {
              k = lb;
              var vt = ib;
            }
          else
            O = A.nodeName, !O || O.toLowerCase() !== "input" || A.type !== "checkbox" && A.type !== "radio" ? C && Oo(C.elementType) && (k = sh) : k = sb;
          if (k && (k = k(t, C))) {
            lh(
              _,
              k,
              n,
              N
            );
            break t;
          }
          vt && vt(t, A, C);
        }
        switch (vt = C ? al(C) : window, t) {
          case "focusin":
            (ih(vt) || vt.contentEditable === "true") && (ri = vt, Xo = C, dl = null);
            break;
          case "focusout":
            dl = Xo = ri = null;
            break;
          case "mousedown":
            Zo = !0;
            break;
          case "contextmenu":
          case "mouseup":
          case "dragend":
            Zo = !1, ph(_, n, N);
            break;
          case "selectionchange":
            if (rb) break;
          case "keydown":
          case "keyup":
            ph(_, n, N);
        }
        var $;
        if (Lo)
          t: {
            switch (t) {
              case "compositionstart":
                var lt = "onCompositionStart";
                break t;
              case "compositionend":
                lt = "onCompositionEnd";
                break t;
              case "compositionupdate":
                lt = "onCompositionUpdate";
                break t;
            }
            lt = void 0;
          }
        else
          oi ? nh(t, n) && (lt = "onCompositionEnd") : t === "keydown" && n.keyCode === 229 && (lt = "onCompositionStart");
        lt && ($d && n.locale !== "ko" && (oi || lt !== "onCompositionStart" ? lt === "onCompositionEnd" && oi && ($ = kd()) : (Zn = N, _o = "value" in Zn ? Zn.value : Zn.textContent, oi = !0)), vt = Cu(C, lt), 0 < vt.length && (lt = new Wd(
          lt,
          t,
          null,
          n,
          N
        ), _.push({ event: lt, listeners: vt }), $ ? lt.data = $ : ($ = ah(n), $ !== null && (lt.data = $)))), ($ = $1 ? tb(t, n) : eb(t, n)) && (lt = Cu(C, "onBeforeInput"), 0 < lt.length && (vt = new Wd(
          "onBeforeInput",
          "beforeinput",
          null,
          n,
          N
        ), _.push({
          event: vt,
          listeners: lt
        }), vt.data = $)), $b(
          _,
          t,
          C,
          n,
          N
        );
      }
      Kp(_, e);
    });
  }
  function Bl(t, e, n) {
    return {
      instance: t,
      listener: e,
      currentTarget: n
    };
  }
  function Cu(t, e) {
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
  function aS(t) {
    if (t === null) return null;
    do
      t = t.return;
    while (t && t.tag !== 5 && t.tag !== 27);
    return t || null;
  }
  function kp(t, e, n, a, s) {
    for (var u = e._reactName, f = []; n !== null && n !== a; ) {
      var m = n, S = m.alternate, C = m.stateNode;
      if (m = m.tag, S !== null && S === a) break;
      m !== 5 && m !== 26 && m !== 27 || C === null || (S = C, s ? (C = il(n, u), C != null && f.unshift(
        Bl(n, C, S)
      )) : s || (C = il(n, u), C != null && f.push(
        Bl(n, C, S)
      ))), n = n.return;
    }
    f.length !== 0 && t.push({ event: e, listeners: f });
  }
  var iS = /\r\n?/g, lS = /\u0000|\uFFFD/g;
  function Pp(t) {
    return (typeof t == "string" ? t : "" + t).replace(iS, `
`).replace(lS, "");
  }
  function Fp(t, e) {
    return e = Pp(e), Pp(t) === e;
  }
  function wt(t, e, n, a, s, u) {
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
        Qd(t, a, u);
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
          typeof u == "function" && (n === "formAction" ? (e !== "input" && wt(t, e, "name", s.name, s, null), wt(
            t,
            e,
            "formEncType",
            s.formEncType,
            s,
            null
          ), wt(
            t,
            e,
            "formMethod",
            s.formMethod,
            s,
            null
          ), wt(
            t,
            e,
            "formTarget",
            s.formTarget,
            s,
            null
          )) : (wt(t, e, "encType", s.encType, s, null), wt(t, e, "method", s.method, s, null), wt(t, e, "target", s.target, s, null)));
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
        a != null && pt("scroll", t);
        return;
      case "onScrollEnd":
        a != null && pt("scrollend", t);
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
        pt("beforetoggle", t), pt("toggle", t), vs(t, "popover", a);
        break;
      case "xlinkActuate":
        Cn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:actuate",
          a
        );
        break;
      case "xlinkArcrole":
        Cn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:arcrole",
          a
        );
        break;
      case "xlinkRole":
        Cn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:role",
          a
        );
        break;
      case "xlinkShow":
        Cn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:show",
          a
        );
        break;
      case "xlinkTitle":
        Cn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:title",
          a
        );
        break;
      case "xlinkType":
        Cn(
          t,
          "http://www.w3.org/1999/xlink",
          "xlink:type",
          a
        );
        break;
      case "xmlBase":
        Cn(
          t,
          "http://www.w3.org/XML/1998/namespace",
          "xml:base",
          a
        );
        break;
      case "xmlLang":
        Cn(
          t,
          "http://www.w3.org/XML/1998/namespace",
          "xml:lang",
          a
        );
        break;
      case "xmlSpace":
        Cn(
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
          n = A1.get(n) || n, vs(t, n, a);
        else return;
    }
    xt = !0;
  }
  function Cc(t, e, n, a, s, u) {
    switch (n) {
      case "style":
        Qd(t, a, u);
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
        a != null && pt("scroll", t);
        return;
      case "onScrollEnd":
        a != null && pt("scrollend", t);
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
        if (!jd.hasOwnProperty(n))
          t: {
            if (n[0] === "o" && n[1] === "n" && (s = n.endsWith("Capture"), u = n.slice(2, s ? n.length - 7 : void 0), e = t[Te] || null, e = e != null ? e[n] : null, typeof e == "function" && t.removeEventListener(u, e, s), typeof a == "function")) {
              typeof e != "function" && e !== null && (n in t ? t[n] = null : t.hasAttribute(n) && t.removeAttribute(n)), t.addEventListener(u, a, s);
              break t;
            }
            xt = !0, n in t ? t[n] = a : a === !0 ? t.setAttribute(n, "") : vs(t, n, a);
          }
        return;
    }
    xt = !0;
  }
  function ce(t, e, n) {
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
        pt("error", t), pt("load", t);
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
                  wt(t, e, u, f, n, null);
              }
          }
        s && wt(t, e, "srcSet", n.srcSet, n, null), a && wt(t, e, "src", n.src, n, null);
        return;
      case "input":
        pt("invalid", t);
        var m = u = f = s = null, S = null, C = null;
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
                  C = N;
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
                  wt(t, e, a, N, n, null);
              }
          }
        qd(
          t,
          u,
          m,
          S,
          C,
          f,
          s,
          !1
        );
        return;
      case "select":
        pt("invalid", t), a = f = u = null;
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
                wt(t, e, s, m, n, null);
            }
        e = u, n = f, t.multiple = !!a, e != null ? ii(t, !!a, e, !1) : n != null && ii(t, !!a, n, !0);
        return;
      case "textarea":
        pt("invalid", t), u = s = a = null;
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
                wt(t, e, f, m, n, null);
            }
        Xd(t, a, s, u);
        return;
      case "option":
        for (S in n)
          n.hasOwnProperty(S) && (a = n[S], a != null) && (S === "selected" ? t.selected = a && typeof a != "function" && typeof a != "symbol" : wt(t, e, S, a, n, null));
        return;
      case "dialog":
        pt("beforetoggle", t), pt("toggle", t), pt("cancel", t), pt("close", t);
        break;
      case "iframe":
      case "object":
        pt("load", t);
        break;
      case "video":
      case "audio":
        for (a = 0; a < Ul.length; a++)
          pt(Ul[a], t);
        break;
      case "image":
        pt("error", t), pt("load", t);
        break;
      case "details":
        pt("toggle", t);
        break;
      case "embed":
      case "source":
      case "link":
        pt("error", t), pt("load", t);
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
        for (C in n)
          if (n.hasOwnProperty(C) && (a = n[C], a != null))
            switch (C) {
              case "children":
              case "dangerouslySetInnerHTML":
                throw Error(o(137, e));
              default:
                wt(t, e, C, a, n, null);
            }
        return;
      default:
        if (Oo(e)) {
          for (N in n)
            n.hasOwnProperty(N) && (a = n[N], a !== void 0 && Cc(
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
      n.hasOwnProperty(m) && (a = n[m], a != null && wt(t, e, m, a, n, null));
  }
  var sS = {};
  function uS(t, e, n, a) {
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
        var s = null, u = null, f = null, m = null, S = null, C = null, N = null;
        for (O in n) {
          var _ = n[O];
          if (n.hasOwnProperty(O) && _ != null)
            switch (O) {
              case "checked":
                break;
              case "value":
                break;
              case "defaultValue":
                S = _;
              default:
                a.hasOwnProperty(O) || wt(t, e, O, null, a, _);
            }
        }
        for (var A in a) {
          var O = a[A];
          if (_ = n[A], a.hasOwnProperty(A) && (O != null || _ != null))
            switch (A) {
              case "type":
                O !== _ && (xt = !0), u = O;
                break;
              case "name":
                O !== _ && (xt = !0), s = O;
                break;
              case "checked":
                O !== _ && (xt = !0), C = O;
                break;
              case "defaultChecked":
                O !== _ && (xt = !0), N = O;
                break;
              case "value":
                O !== _ && (xt = !0), f = O;
                break;
              case "defaultValue":
                O !== _ && (xt = !0), m = O;
                break;
              case "children":
              case "dangerouslySetInnerHTML":
                if (O != null)
                  throw Error(o(137, e));
                break;
              default:
                O !== _ && wt(
                  t,
                  e,
                  A,
                  O,
                  a,
                  _
                );
            }
        }
        Co(
          t,
          f,
          m,
          S,
          C,
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
                a.hasOwnProperty(u) || wt(
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
                u !== S && (xt = !0), A = u;
                break;
              case "defaultValue":
                u !== S && (xt = !0), m = u;
                break;
              case "multiple":
                u !== S && (xt = !0), f = u;
              default:
                u !== S && wt(
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
                wt(t, e, m, null, a, s);
            }
        for (f in a)
          if (s = a[f], u = n[f], a.hasOwnProperty(f) && (s != null || u != null))
            switch (f) {
              case "value":
                s !== u && (xt = !0), A = s;
                break;
              case "defaultValue":
                s !== u && (xt = !0), O = s;
                break;
              case "children":
                break;
              case "dangerouslySetInnerHTML":
                if (s != null) throw Error(o(91));
                break;
              default:
                s !== u && wt(t, e, f, s, a, u);
            }
        Gd(t, A, O);
        return;
      case "option":
        for (var G in n)
          A = n[G], n.hasOwnProperty(G) && A != null && !a.hasOwnProperty(G) && (G === "selected" ? t.selected = !1 : wt(
            t,
            e,
            G,
            null,
            a,
            A
          ));
        for (S in a)
          A = a[S], O = n[S], a.hasOwnProperty(S) && A !== O && (A != null || O != null) && (S === "selected" ? (A !== O && (xt = !0), t.selected = A && typeof A != "function" && typeof A != "symbol") : wt(
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
          A = n[P], n.hasOwnProperty(P) && A != null && !a.hasOwnProperty(P) && wt(t, e, P, null, a, A);
        for (C in a)
          if (A = a[C], O = n[C], a.hasOwnProperty(C) && A !== O && (A != null || O != null))
            switch (C) {
              case "children":
              case "dangerouslySetInnerHTML":
                if (A != null)
                  throw Error(o(137, e));
                break;
              default:
                wt(
                  t,
                  e,
                  C,
                  A,
                  a,
                  O
                );
            }
        return;
      default:
        if (Oo(e)) {
          for (var ct in n)
            A = n[ct], n.hasOwnProperty(ct) && A !== void 0 && !a.hasOwnProperty(ct) && Cc(
              t,
              e,
              ct,
              void 0,
              a,
              A
            );
          for (N in a)
            A = a[N], O = n[N], !a.hasOwnProperty(N) || A === O || A === void 0 && O === void 0 || Cc(
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
      A = n[M], n.hasOwnProperty(M) && A != null && !a.hasOwnProperty(M) && wt(t, e, M, null, a, A);
    for (_ in a)
      A = a[_], O = n[_], !a.hasOwnProperty(_) || A === O || A == null && O == null || wt(t, e, _, A, a, O);
  }
  function Wp(t) {
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
  function oS() {
    if (typeof performance.getEntriesByType == "function") {
      for (var t = 0, e = 0, n = performance.getEntriesByType("resource"), a = 0; a < n.length; a++) {
        var s = n[a], u = s.transferSize, f = s.initiatorType, m = s.duration;
        if (u && m && Wp(f)) {
          for (f = 0, m = s.responseEnd, a += 1; a < n.length; a++) {
            var S = n[a], C = S.startTime;
            if (C > m) break;
            var N = S.transferSize, _ = S.initiatorType;
            N && Wp(_) && (S = S.responseEnd, f += N * (S < m ? 1 : (m - C) / (S - C)));
          }
          if (--a, e += 8 * (u + f) / (s.duration / 1e3), t++, 10 < t) break;
        }
      }
      if (0 < t) return e / t / 1e6;
    }
    return navigator.connection && (t = navigator.connection.downlink, typeof t == "number") ? t : 5;
  }
  var Dc = null, Oc = null;
  function Ll(t) {
    return t.nodeType === 9 ? t : t.ownerDocument;
  }
  function Ip(t) {
    switch (t) {
      case "http://www.w3.org/2000/svg":
        return 1;
      case "http://www.w3.org/1998/Math/MathML":
        return 2;
      default:
        return 0;
    }
  }
  function $p(t, e) {
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
  function ty(t, e, n, a) {
    return n = Ll(
      n
    ).createElement(t), n[le] = a, n[Te] = e, ce(n, t, e), te(n), n;
  }
  function Nc(t, e) {
    return t === "textarea" || t === "noscript" || typeof e.children == "string" || typeof e.children == "number" || typeof e.children == "bigint" || typeof e.dangerouslySetInnerHTML == "object" && e.dangerouslySetInnerHTML !== null && e.dangerouslySetInnerHTML.__html != null;
  }
  var wc = null;
  function rS() {
    var t = window.event;
    return t && t.type === "popstate" ? t === wc ? !1 : (wc = t, !0) : (wc = null, !1);
  }
  var Rc = typeof setTimeout == "function" ? setTimeout : void 0, cS = typeof clearTimeout == "function" ? clearTimeout : void 0, ey = typeof Promise == "function" ? Promise : void 0, ny = typeof requestAnimationFrame == "function" ? requestAnimationFrame : Rc, fS = typeof queueMicrotask == "function" ? queueMicrotask : typeof ey < "u" ? function(t) {
    return ey.resolve(null).then(t).catch(dS);
  } : Rc;
  function dS(t) {
    setTimeout(function() {
      throw t;
    });
  }
  function ca(t) {
    return t === "head";
  }
  function ay(t, e) {
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
          Hc(
            t.ownerDocument.documentElement
          );
        else if (n === "head") {
          n = t.ownerDocument.head, Hc(n);
          for (var u = n.firstChild; u; ) {
            var f = u.nextSibling, m = u.nodeName;
            u[nl] || m === "SCRIPT" || m === "STYLE" || m === "LINK" && u.rel.toLowerCase() === "stylesheet" || n.removeChild(u), u = f;
          }
        } else
          n === "body" && Hc(t.ownerDocument.body);
      n = s;
    } while (n);
    Gi(e);
  }
  function iy(t, e) {
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
  function ly(t, e, n) {
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
  function sy(t, e) {
    t = t.style, e = e.style;
    var n = e != null ? e.hasOwnProperty("viewTransitionName") ? e.viewTransitionName : e.hasOwnProperty("view-transition-name") ? e["view-transition-name"] : null : null;
    t.viewTransitionName = n == null || typeof n == "boolean" ? "" : ("" + n).trim(), n = e != null ? e.hasOwnProperty("viewTransitionClass") ? e.viewTransitionClass : e.hasOwnProperty("view-transition-class") ? e["view-transition-class"] : null : null, t.viewTransitionClass = n == null || typeof n == "boolean" ? "" : ("" + n).trim(), t.display === "inline-block" && (e == null ? t.display = t.margin = "" : (n = e.display, t.display = n == null || typeof n == "boolean" ? "" : n, n = e.margin, n != null ? t.margin = n : (n = e.hasOwnProperty("marginTop") ? e.marginTop : e["margin-top"], t.marginTop = n == null || typeof n == "boolean" ? "" : n, e = e.hasOwnProperty("marginBottom") ? e.marginBottom : e["margin-bottom"], t.marginBottom = e == null || typeof e == "boolean" ? "" : e)));
  }
  function hS(t, e, n) {
    return n = n.ownerDocument.defaultView, {
      rect: t,
      abs: e.position === "absolute" || e.position === "fixed",
      clip: e.clipPath !== "none" || e.overflow !== "visible" || e.filter !== "none" || e.mask !== "none" || e.mask !== "none" || e.borderRadius !== "0px",
      view: 0 <= t.bottom && 0 <= t.right && t.top <= n.innerHeight && t.left <= n.innerWidth
    };
  }
  function zc(t) {
    var e = t.getBoundingClientRect(), n = getComputedStyle(t);
    return hS(e, n, t);
  }
  function mS(t) {
    return t.documentElement.clientHeight;
  }
  function pS(t) {
    this.addEventListener("load", t), this.addEventListener("error", t);
  }
  function yS(t, e, n, a, s, u, f, m, S) {
    var C = e.nodeType === 9 ? e : e.ownerDocument;
    try {
      var N = C.startViewTransition({
        update: function() {
          var A = C.defaultView, O = A.navigation && A.navigation.transition, G = C.fonts.status;
          a();
          var P = [];
          if (G === "loaded" && (mS(C), C.fonts.status === "loading" && P.push(C.fonts.ready)), G = P.length, t !== null)
            for (var ct = t.suspenseyImages, M = 0, x = 0; x < ct.length; x++) {
              var D = ct[x];
              if (!D.complete) {
                var z = D.getBoundingClientRect();
                if (0 < z.bottom && 0 < z.right && z.top < A.innerHeight && z.left < A.innerWidth) {
                  if (M += Dy(D), M > Nu) {
                    P.length = G;
                    break;
                  }
                  D = new Promise(
                    pS.bind(D)
                  ), P.push(D);
                }
              }
            }
          if (0 < P.length)
            return A = Promise.race([
              Promise.all(P),
              new Promise(function(k) {
                return setTimeout(k, 500);
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
      C.__reactViewTransition = N;
      var _ = [];
      return N.ready.then(
        function() {
          for (var A = C.documentElement.getAnimations({
            subtree: !0
          }), O = 0; O < A.length; O++) {
            var G = A[O], P = G.effect, ct = P.pseudoElement;
            if (ct != null && ct.startsWith("::view-transition")) {
              _.push(G), G = P.getKeyframes();
              for (var M = ct = void 0, x = !0, D = 0; D < G.length; D++) {
                var z = G[D], k = z.width;
                if (ct === void 0) ct = k;
                else if (ct !== k) {
                  x = !1;
                  break;
                }
                if (k = z.height, M === void 0) M = k;
                else if (M !== k) {
                  x = !1;
                  break;
                }
                delete z.width, delete z.height, z.transform === "none" && delete z.transform;
              }
              x && ct !== void 0 && M !== void 0 && (P.setKeyframes(G), x = getComputedStyle(
                P.target,
                P.pseudoElement
              ), x.width !== ct || x.height !== M) && (x = G[0], x.width = ct, x.height = M, x = G[G.length - 1], x.width = ct, x.height = M, P.setKeyframes(G));
            }
          }
          f();
        },
        function(A) {
          C.__reactViewTransition === N && (C.__reactViewTransition = null);
          try {
            typeof A == "object" && A !== null && A.name === "InvalidStateError" && (A.message === "View transition was skipped because document visibility state is hidden." || A.message === "Skipping view transition because document visibility state has become hidden." || A.message === "Skipping view transition because viewport size changed." || A.message === "Transition was aborted because of invalid state") && (A = null), A !== null && S(A);
          } finally {
            a(), s(), f();
          }
        }
      ), N.finished.finally(function() {
        for (var A = 0; A < _.length; A++)
          _[A].cancel();
        C.__reactViewTransition === N && (C.__reactViewTransition = null), m();
      }), N;
    } catch {
      return a(), s(), f(), null;
    }
  }
  function Za(t, e) {
    this._scope = document.documentElement, this._selector = "::view-transition-" + t + "(" + e + ")";
  }
  Za.prototype.animate = function(t, e) {
    return e = typeof e == "number" ? { duration: e } : J({}, e), e.pseudoElement = this._selector, this._scope.animate(t, e);
  }, Za.prototype.getAnimations = function() {
    for (var t = this._scope, e = this._selector, n = t.getAnimations({ subtree: !0 }), a = [], s = 0; s < n.length; s++) {
      var u = n[s].effect;
      u !== null && u.target === t && u.pseudoElement === e && a.push(n[s]);
    }
    return a;
  }, Za.prototype.getComputedStyle = function() {
    return getComputedStyle(this._scope, this._selector);
  };
  function uy(t) {
    return {
      name: t,
      group: new Za("group", t),
      imagePair: new Za("image-pair", t),
      old: new Za("old", t),
      new: new Za("new", t)
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
      if (ry(u, t, e, n) === -1) {
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
        }), y(
          this._fragmentFiber.child,
          !1,
          gS,
          t,
          m,
          a
        );
      }
      this._eventListeners = u;
    }
  };
  function gS(t, e, n, a) {
    return j(t).addEventListener(
      e,
      n,
      a
    ), !1;
  }
  Be.prototype.removeEventListener = function(t, e, n) {
    var a = this._eventListeners;
    if (a !== null && (e = ry(
      a,
      t,
      e,
      n
    ), e !== -1)) {
      var s = a[e];
      n = s.attachedListener;
      var u = s.cleanup;
      s = Ui(s.optionsOrUseCapture), y(
        this._fragmentFiber.child,
        !1,
        vS,
        t,
        n,
        s
      ), a.splice(e, 1), u !== null && u();
    }
  };
  function vS(t, e, n, a) {
    return j(t).removeEventListener(
      e,
      n,
      a
    ), !1;
  }
  function Ui(t) {
    return t != null && typeof t != "boolean" && (t.once === !0 || t.signal instanceof AbortSignal) ? { capture: t.capture, passive: t.passive } : t;
  }
  function oy(t) {
    return t == null ? "c=0" : typeof t == "boolean" ? "c=" + (t ? "1" : "0") : "c=" + (t.capture ? "1" : "0");
  }
  function ry(t, e, n, a) {
    if (t.length === 0) return -1;
    a = oy(a);
    for (var s = 0; s < t.length; s++) {
      var u = t[s];
      if (u.type === e && u.listener === n && oy(u.optionsOrUseCapture) === a)
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
    y(
      this._fragmentFiber.child,
      !0,
      cy,
      t,
      void 0,
      void 0
    );
  };
  function cy(t, e) {
    return t.tag === 6 ? !1 : (t = j(t), wS(t, e));
  }
  Be.prototype.focusLast = function(t) {
    var e = [];
    y(
      this._fragmentFiber.child,
      !0,
      _c,
      e,
      void 0,
      void 0
    );
    for (var n = e.length - 1; 0 <= n && !cy(e[n], t); n--) ;
  };
  function _c(t, e) {
    return e.push(t), !1;
  }
  Be.prototype.blur = function() {
    var t = T(
      this._fragmentFiber
    );
    t !== null && (t = j(t), t = Ll(t).activeElement, t !== null && y(
      this._fragmentFiber.child,
      !1,
      bS,
      t,
      void 0,
      void 0
    ));
  };
  function bS(t, e) {
    return t.tag === 6 ? !1 : (t = j(t), t === e || t.contains(e) ? (e.blur(), !0) : !1);
  }
  Be.prototype.observeUsing = function(t) {
    this._observers === null && (this._observers = /* @__PURE__ */ new Set()), this._observers.add(t), y(
      this._fragmentFiber.child,
      !1,
      SS,
      t,
      void 0,
      void 0
    );
  };
  function SS(t, e) {
    return t.tag === 6 || (t = j(t), e.observe(t)), !1;
  }
  Be.prototype.unobserveUsing = function(t) {
    var e = this._observers;
    if (e !== null && e.has(t)) {
      e.delete(t), y(
        this._fragmentFiber.child,
        !1,
        TS,
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
  function TS(t, e) {
    return t.tag === 6 || (t = j(t), e.unobserve(t)), !1;
  }
  var nn = [], Vc = !1;
  function xS(t, e, n) {
    nn.push({
      fragmentInstance: t,
      observer: e,
      instance: n
    }), Vc || (Vc = !0, RS(function() {
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
    return y(
      this._fragmentFiber.child,
      !1,
      ES,
      t,
      void 0,
      void 0
    ), t;
  };
  function ES(t, e) {
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
    y(
      this._fragmentFiber.child,
      !1,
      _c,
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
      return n === t ? s = Node.DOCUMENT_POSITION_CONTAINS : a & Node.DOCUMENT_POSITION_CONTAINED_BY && (n = R(e)[1], n === null ? s = Node.DOCUMENT_POSITION_PRECEDING : (t = j(n).compareDocumentPosition(
        t
      ), s = t === 0 || t & Node.DOCUMENT_POSITION_FOLLOWING ? Node.DOCUMENT_POSITION_FOLLOWING : Node.DOCUMENT_POSITION_PRECEDING)), s |= Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC;
    }
    e = j(n[0]), s = j(n[n.length - 1]);
    var u = V(this._fragmentFiber) ? e.parentElement : a;
    if (u == null)
      return Node.DOCUMENT_POSITION_DISCONNECTED;
    a = u.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_CONTAINED_BY, u = u.compareDocumentPosition(s) & Node.DOCUMENT_POSITION_CONTAINED_BY;
    var f = e.compareDocumentPosition(t), m = s.compareDocumentPosition(t), S = f & Node.DOCUMENT_POSITION_CONTAINED_BY || m & Node.DOCUMENT_POSITION_CONTAINED_BY;
    return m = a && u && f & Node.DOCUMENT_POSITION_FOLLOWING && m & Node.DOCUMENT_POSITION_PRECEDING, e = a && e === t || u && s === t || S || m ? Node.DOCUMENT_POSITION_CONTAINED_BY : !a && e === t || !u && s === t ? Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC : f, e & Node.DOCUMENT_POSITION_DISCONNECTED || e & Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC || AS(
      e,
      this._fragmentFiber,
      n[0],
      n[n.length - 1],
      t
    ) ? e : Node.DOCUMENT_POSITION_IMPLEMENTATION_SPECIFIC;
  };
  function AS(t, e, n, a, s) {
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
    return t & Node.DOCUMENT_POSITION_PRECEDING ? ((e = !!u) && !(e = u === n) && (e = dt(
      n,
      u,
      it
    ), e === null ? e = !1 : (y(
      e,
      !0,
      X,
      u,
      n
    ), u = H, H = null, e = u !== null)), e) : t & Node.DOCUMENT_POSITION_FOLLOWING ? ((e = !!u) && !(e = u === a) && (e = dt(
      a,
      u,
      it
    ), e === null ? e = !1 : (y(
      e,
      !0,
      Q,
      u,
      a
    ), u = H, q = H = null, e = u !== null)), e) : !1;
  }
  function fy(t, e) {
    var n = t.ownerDocument.createRange();
    n.selectNodeContents(t), t = n.getBoundingClientRect(), window.scrollTo(
      window.scrollX + t.left,
      e ? window.scrollY + t.top : window.scrollY + t.bottom - window.innerHeight
    );
  }
  Be.prototype.scrollIntoView = function(t) {
    if (typeof t == "object") throw Error(o(566));
    var e = [];
    y(
      this._fragmentFiber.child,
      !1,
      _c,
      e,
      void 0,
      void 0
    );
    var n = t !== !1;
    if (e.length === 0) {
      var a = R(
        this._fragmentFiber
      );
      if (a = n ? a[1] || a[0] || T(this._fragmentFiber) : a[0] || a[1], a === null) return;
      if (a.tag === 6) {
        t = j(a), fy(t, n);
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
      s.tag === 6 ? (s = j(s), fy(s, n)) : j(s).scrollIntoView(t), a += n ? -1 : 1;
    }
  };
  function MS(t, e) {
    return t = j(t), dy(t, e), !1;
  }
  function dy(t, e) {
    t.reactFragments == null && (t.reactFragments = /* @__PURE__ */ new Set()), t.reactFragments.add(e);
  }
  function hy(t, e) {
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
    }), dy(t, e));
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
      typeof u.rootMargin == "string" ? xS(
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
  function DS(t, e, n, a) {
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
  function OS(t, e, n) {
    if (e === "") return null;
    for (; t.nodeType !== 3; )
      if ((t.nodeType !== 1 || t.nodeName !== "INPUT" || t.type !== "hidden") && !n || (t = Ke(t.nextSibling), t === null)) return null;
    return t;
  }
  function my(t, e) {
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
  function NS(t, e) {
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
  var Lc = null;
  function py(t) {
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
  function yy(t) {
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
  function wS(t, e) {
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
  function RS(t) {
    ny(function() {
      ny(function(e) {
        return t(e);
      });
    });
  }
  function gy(t, e, n) {
    switch (e = Ll(n), t) {
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
  function vy(t, e, n) {
    for (var a in n) {
      var s = n[a];
      n.hasOwnProperty(a) && s != null && wt(t, e, a, null, sS, s);
    }
    n.dangerouslySetInnerHTML != null && (t.textContent = ""), t.onclick === rn && (t.onclick = null), gs(t);
  }
  function Hc(t) {
    for (var e = t.attributes; e.length; )
      t.removeAttributeNode(e[0]);
    gs(t);
  }
  var Je = /* @__PURE__ */ new Map(), by = /* @__PURE__ */ new Set();
  function Hl(t) {
    if (typeof t.getRootNode == "function") {
      var e = t.getRootNode();
      if (e.nodeType === 9 || e.nodeType === 11) return e;
    }
    return t.nodeType === 9 ? t : t.ownerDocument;
  }
  var Hn = st.d;
  st.d = {
    f: zS,
    r: _S,
    D: VS,
    C: jS,
    L: US,
    m: BS,
    X: HS,
    S: LS,
    M: YS
  };
  function zS() {
    var t = Hn.f(), e = Su();
    return t || e;
  }
  function _S(t) {
    var e = ei(t);
    e !== null && e.tag === 5 && e.type === "form" ? Tm(e) : Hn.r(t);
  }
  var Bi = typeof document > "u" ? null : document;
  function Sy(t, e, n) {
    var a = Bi;
    if (a && typeof e == "string" && e) {
      var s = He(e);
      s = 'link[rel="' + t + '"][href="' + s + '"]', typeof n == "string" && (s += '[crossorigin="' + n + '"]'), by.has(s) || (by.add(s), t = { rel: t, crossOrigin: n, href: e }, a.querySelector(s) === null && (e = a.createElement("link"), ce(e, "link", t), te(e), a.head.appendChild(e)));
    }
  }
  function VS(t) {
    Hn.D(t), Sy("dns-prefetch", t, null);
  }
  function jS(t, e) {
    Hn.C(t, e), Sy("preconnect", t, e);
  }
  function US(t, e, n) {
    Hn.L(t, e, n);
    var a = Bi;
    if (a && t && e) {
      var s = 'link[rel="preload"][as="' + He(e) + '"]';
      e === "image" && n && n.imageSrcSet ? (s += '[imagesrcset="' + He(
        n.imageSrcSet
      ) + '"]', typeof n.imageSizes == "string" && (s += '[imagesizes="' + He(
        n.imageSizes
      ) + '"]')) : s += '[href="' + He(t) + '"]';
      var u = s;
      switch (e) {
        case "style":
          u = Li(t);
          break;
        case "script":
          u = Hi(t);
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
        ce(f, "link", t), e === "style" && (f[ys] = !0, f.onload = f.onerror = function() {
          _d(f);
        }), te(f), a.head.appendChild(f);
      }
    }
  }
  function BS(t, e) {
    Hn.m(t, e);
    var n = Bi;
    if (n && t) {
      var a = e && typeof e.as == "string" ? e.as : "script", s = 'link[rel="modulepreload"][as="' + He(a) + '"][href="' + He(t) + '"]', u = s;
      switch (a) {
        case "audioworklet":
        case "paintworklet":
        case "serviceworker":
        case "sharedworker":
        case "worker":
        case "script":
          u = Hi(t);
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
        a = n.createElement("link"), ce(a, "link", t), te(a), n.head.appendChild(a);
      }
    }
  }
  function LS(t, e, n) {
    Hn.S(t, e, n);
    var a = Bi;
    if (a && t) {
      var s = ni(a).hoistableStyles, u = Li(t);
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
          te(S), ce(S, "link", t), S._p = new Promise(function(C, N) {
            S.onload = C, S.onerror = N;
          }), S.addEventListener("load", function() {
            m.loading |= 1;
          }), S.addEventListener("error", function() {
            m.loading |= 2;
          }), m.loading |= 4, Du(f, e, a);
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
  function HS(t, e) {
    Hn.X(t, e);
    var n = Bi;
    if (n && t) {
      var a = ni(n).hoistableScripts, s = Hi(t), u = a.get(s);
      u || (u = n.querySelector(ql(s)), u || (t = J({ src: t, async: !0 }, e), (e = Je.get(s)) && qc(t, e), u = n.createElement("script"), te(u), ce(u, "link", t), n.head.appendChild(u)), u = {
        type: "script",
        instance: u,
        count: 1,
        state: null
      }, a.set(s, u));
    }
  }
  function YS(t, e) {
    Hn.M(t, e);
    var n = Bi;
    if (n && t) {
      var a = ni(n).hoistableScripts, s = Hi(t), u = a.get(s);
      u || (u = n.querySelector(ql(s)), u || (t = J({ src: t, async: !0, type: "module" }, e), (e = Je.get(s)) && qc(t, e), u = n.createElement("script"), te(u), ce(u, "link", t), n.head.appendChild(u)), u = {
        type: "script",
        instance: u,
        count: 1,
        state: null
      }, a.set(s, u));
    }
  }
  function Ty(t, e, n, a) {
    var s = (s = qn.current) ? Hl(s) : null;
    if (!s) throw Error(o(446));
    switch (t) {
      case "meta":
      case "title":
        return null;
      case "style":
        return typeof n.precedence == "string" && typeof n.href == "string" ? (n = Li(n.href), e = ni(
          s
        ).hoistableStyles, a = e.get(n), a || (a = {
          type: "style",
          instance: null,
          count: 0,
          state: null
        }, e.set(n, a)), a) : { type: "void", instance: null, count: 0, state: null };
      case "link":
        if (n.rel === "stylesheet" && typeof n.href == "string" && typeof n.precedence == "string") {
          t = Li(n.href);
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
          }, Je.set(t, u)), qS(
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
        return e = n.async, n = n.src, typeof n == "string" && e && typeof e != "function" && typeof e != "symbol" ? (n = Hi(n), e = ni(
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
  function Li(t) {
    return 'href="' + He(t) + '"';
  }
  function Yl(t) {
    return 'link[rel="stylesheet"][' + t + "]";
  }
  function xy(t) {
    return J({}, t, {
      "data-precedence": t.precedence,
      precedence: null
    });
  }
  function qS(t, e, n, a) {
    if (e = t.querySelector(
      'link[rel="preload"][as="style"][' + e + "]"
    )) {
      if (e[ys] !== !0) {
        a.loading = 1;
        return;
      }
    } else
      e = t.createElement("link"), e[ys] = !0, e.onload = e.onerror = _d.bind(null, e), ce(e, "link", n), te(e), t.head.appendChild(e);
    a.preload = e, e.addEventListener("load", function() {
      return a.loading |= 1;
    }), e.addEventListener("error", function() {
      return a.loading |= 2;
    });
  }
  function Hi(t) {
    return '[src="' + He(t) + '"]';
  }
  function ql(t) {
    return "script[async]" + t;
  }
  function Ey(t, e, n) {
    if (e.count++, e.instance === null)
      switch (e.type) {
        case "style":
          var a = t.querySelector(
            'style[data-href~="' + He(n.href) + '"]'
          );
          if (a)
            return e.instance = a, te(a), a;
          var s = J({}, n, {
            "data-href": n.href,
            "data-precedence": n.precedence,
            href: null,
            precedence: null
          });
          return a = (t.ownerDocument || t).createElement(
            "style"
          ), te(a), ce(a, "style", s), Du(a, n.precedence, t), e.instance = a;
        case "stylesheet":
          s = Li(n.href);
          var u = t.querySelector(
            Yl(s)
          );
          if (u)
            return e.state.loading |= 4, e.instance = u, te(u), u;
          a = xy(n), (s = Je.get(s)) && Yc(a, s), u = (t.ownerDocument || t).createElement("link"), te(u);
          var f = u;
          return f._p = new Promise(function(m, S) {
            f.onload = m, f.onerror = S;
          }), ce(u, "link", a), e.state.loading |= 4, Du(u, n.precedence, t), e.instance = u;
        case "script":
          return u = Hi(n.src), (s = t.querySelector(
            ql(u)
          )) ? (e.instance = s, te(s), s) : (a = n, (s = Je.get(u)) && (a = J({}, n), qc(a, s)), t = t.ownerDocument || t, s = t.createElement("script"), te(s), ce(s, "link", a), t.head.appendChild(s), e.instance = s);
        case "void":
          return null;
        default:
          throw Error(o(443, e.type));
      }
    else
      e.type === "stylesheet" && (e.state.loading & 4) === 0 && (a = e.instance, e.state.loading |= 4, Du(a, n.precedence, t));
    return e.instance;
  }
  function Du(t, e, n) {
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
  function Ay(t, e, n) {
    if (Ou === null) {
      var a = /* @__PURE__ */ new Map(), s = Ou = /* @__PURE__ */ new Map();
      s.set(n, a);
    } else
      s = Ou, a = s.get(n), a || (a = /* @__PURE__ */ new Map(), s.set(n, a));
    if (a.has(t)) return a;
    for (a.set(t, null), n = n.getElementsByTagName(t), s = 0; s < n.length; s++) {
      var u = n[s];
      if (!(u[nl] || u[le] || t === "link" && u.getAttribute("rel") === "stylesheet") && u.namespaceURI !== "http://www.w3.org/2000/svg") {
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
  function GS(t, e, n) {
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
  function My(t, e) {
    return t === "img" && e.src != null && e.src !== "" && e.onLoad == null && e.loading !== "lazy";
  }
  function Cy(t) {
    return !(t.type === "stylesheet" && (t.state.loading & 3) === 0);
  }
  function Dy(t) {
    return (t.width || 100) * (t.height || 100) * (typeof devicePixelRatio == "number" ? devicePixelRatio : 1) * 0.25;
  }
  function Oy(t, e) {
    typeof e.decode == "function" && (t.imgCount++, e.complete || (t.imgBytes += Dy(e), t.suspenseyImages.push(e)), t = QS.bind(t), e.decode().then(t, t));
  }
  function XS(t, e, n, a) {
    if (n.type === "stylesheet" && (typeof a.media != "string" || matchMedia(a.media).matches !== !1) && (n.state.loading & 4) === 0) {
      if (n.instance === null) {
        var s = Li(a.href), u = e.querySelector(
          Yl(s)
        );
        if (u) {
          e = u._p, e !== null && typeof e == "object" && typeof e.then == "function" && (t.count++, t = Gl.bind(t), e.then(t, t)), n.state.loading |= 4, n.instance = u, te(u);
          return;
        }
        u = e.ownerDocument || e, a = xy(a), (s = Je.get(s)) && Yc(a, s), u = u.createElement("link"), te(u);
        var f = u;
        f._p = new Promise(function(m, S) {
          f.onload = m, f.onerror = S;
        }), ce(u, "link", a), n.instance = u;
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
      0 < t.imgBytes && Nu === 0 && (Nu = 62500 * oS());
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
  function Ny(t) {
    if (t.count === 0 && (t.imgCount === 0 || !t.waitingForImages)) {
      if (t.stylesheets) Ru(t, t.stylesheets);
      else if (t.unsuspend) {
        var e = t.unsuspend;
        t.unsuspend = null, e();
      }
    }
  }
  function Gl() {
    this.count--, Ny(this);
  }
  function QS() {
    this.imgCount--, Ny(this);
  }
  var wu = null;
  function Ru(t, e) {
    t.stylesheets = null, t.unsuspend !== null && (t.count++, wu = /* @__PURE__ */ new Map(), e.forEach(KS, t), wu = null, Gl.call(t));
  }
  function KS(t, e) {
    if (!(e.state.loading & 4)) {
      var n = wu.get(t);
      if (n) var a = n.get(null);
      else {
        n = /* @__PURE__ */ new Map(), wu.set(t, n);
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
    $$typeof: Ct,
    Provider: null,
    Consumer: null,
    _currentValue: An,
    _currentValue2: An,
    _threadCount: 0
  };
  function JS(t, e, n, a, s, u, f, m, S) {
    this.tag = 1, this.containerInfo = t, this.pingCache = this.current = this.pendingChildren = null, this.timeoutHandle = -1, this.callbackNode = this.next = this.pendingContext = this.context = this.cancelPendingCommit = null, this.callbackPriority = 0, this.expirationTimes = xo(-1), this.entangledLanes = this.shellSuspendCounter = this.errorRecoveryDisabledLanes = this.expiredLanes = this.warmLanes = this.pingedLanes = this.suspendedLanes = this.pendingLanes = 0, this.entanglements = xo(0), this.hiddenUpdates = xo(null), this.identifierPrefix = a, this.onUncaughtError = s, this.onCaughtError = u, this.onRecoverableError = f, this.pooledCache = null, this.pooledCacheLanes = 0, this.formState = S, this.transitionTypes = null, this.incompleteTransitions = /* @__PURE__ */ new Map();
  }
  function wy(t, e, n, a, s, u, f, m, S, C, N, _) {
    return t = new JS(
      t,
      e,
      n,
      f,
      S,
      C,
      N,
      _,
      m
    ), e = 1, u === !0 && (e |= 24), u = xe(3, null, null, e), t.current = u, u.stateNode = t, e = ar(), e.refCount++, t.pooledCache = e, e.refCount++, u.memoizedState = {
      element: a,
      isDehydrated: n,
      cache: e
    }, ur(u), t;
  }
  function Ry(t) {
    return t ? (t = di, t) : di;
  }
  function zy(t, e, n, a, s, u) {
    s = Ry(s), a.context === null ? a.context = s : a.pendingContext = s, a = In(e), a.payload = { element: n }, u = u === void 0 ? null : u, u !== null && (a.callback = u), n = $n(t, a, e), n !== null && (Ce(n, t, e), bl(n, t, e));
  }
  function _y(t, e) {
    if (t = t.memoizedState, t !== null && t.dehydrated !== null) {
      var n = t.retryLane;
      t.retryLane = n !== 0 && n < e ? n : e;
    }
  }
  function Xc(t, e) {
    _y(t, e), (t = t.alternate) && _y(t, e);
  }
  function Vy(t) {
    if (t.tag === 13 || t.tag === 31) {
      var e = Da(t, 67108864);
      e !== null && Ce(e, t, 67108864), Xc(t, 67108864);
    }
  }
  function jy(t) {
    if (t.tag === 13 || t.tag === 31) {
      var e = Ue();
      e = Eo(e);
      var n = Da(t, e);
      n !== null && Ce(n, t, e), Xc(t, e);
    }
  }
  var qi = !0;
  function kS(t, e, n, a) {
    var s = I.T;
    I.T = null;
    var u = st.p;
    try {
      st.p = 2, Zc(t, e, n, a);
    } finally {
      st.p = u, I.T = s;
    }
  }
  function PS(t, e, n, a) {
    var s = I.T;
    I.T = null;
    var u = st.p;
    try {
      st.p = 8, Zc(t, e, n, a);
    } finally {
      st.p = u, I.T = s;
    }
  }
  function Zc(t, e, n, a) {
    if (qi) {
      var s = Qc(a);
      if (s === null)
        Mc(
          t,
          e,
          a,
          zu,
          n
        ), By(t, a);
      else if (WS(
        s,
        t,
        e,
        n,
        a
      ))
        a.stopPropagation();
      else if (By(t, a), e & 4 && -1 < FS.indexOf(t)) {
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
                    bn(u), (At & 6) === 0 && (gu = De() + 500, jl(0));
                  }
                }
                break;
              case 31:
              case 13:
                m = Da(u, 2), m !== null && Ce(m, u, 2), Su(), Xc(u, 2);
            }
          if (u = Qc(a), u === null && Mc(
            t,
            e,
            a,
            zu,
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
  function Qc(t) {
    return t = wo(t), Kc(t);
  }
  var zu = null;
  function Kc(t) {
    if (zu = null, t = Ea(t), t !== null) {
      var e = h(t);
      if (e === null) t = null;
      else {
        var n = e.tag;
        if (n === 13) {
          if (t = d(e), t !== null) return t;
          t = null;
        } else if (n === 31) {
          if (t = p(e), t !== null) return t;
          t = null;
        } else if (n === 3) {
          if (e.stateNode.current.memoizedState.isDehydrated)
            return e.tag === 3 ? e.stateNode.containerInfo : null;
          t = null;
        } else e !== t && (t = null);
      }
    }
    return zu = t, null;
  }
  function Uy(t) {
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
        switch (o1()) {
          case Td:
            return 2;
          case xd:
            return 8;
          case fs:
          case r1:
            return 32;
          case Ed:
            return 268435456;
          default:
            return 32;
        }
      default:
        return 32;
    }
  }
  var Jc = !1, fa = null, da = null, ha = null, Xl = /* @__PURE__ */ new Map(), Zl = /* @__PURE__ */ new Map(), ma = [], FS = "mousedown mouseup touchcancel touchend touchstart auxclick dblclick pointercancel pointerdown pointerup dragend dragstart drop compositionend compositionstart keydown keypress keyup input textInput copy cut paste click change contextmenu reset".split(
    " "
  );
  function By(t, e) {
    switch (t) {
      case "focusin":
      case "focusout":
        fa = null;
        break;
      case "dragenter":
      case "dragleave":
        da = null;
        break;
      case "mouseover":
      case "mouseout":
        ha = null;
        break;
      case "pointerover":
      case "pointerout":
        Xl.delete(e.pointerId);
        break;
      case "gotpointercapture":
      case "lostpointercapture":
        Zl.delete(e.pointerId);
    }
  }
  function Ql(t, e, n, a, s, u) {
    return t === null || t.nativeEvent !== u ? (t = {
      blockedOn: e,
      domEventName: n,
      eventSystemFlags: a,
      nativeEvent: u,
      targetContainers: [s]
    }, e !== null && (e = ei(e), e !== null && Vy(e)), t) : (t.eventSystemFlags |= a, e = t.targetContainers, s !== null && e.indexOf(s) === -1 && e.push(s), t);
  }
  function WS(t, e, n, a, s) {
    switch (e) {
      case "focusin":
        return fa = Ql(
          fa,
          t,
          e,
          n,
          a,
          s
        ), !0;
      case "dragenter":
        return da = Ql(
          da,
          t,
          e,
          n,
          a,
          s
        ), !0;
      case "mouseover":
        return ha = Ql(
          ha,
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
          Ql(
            Xl.get(u) || null,
            t,
            e,
            n,
            a,
            s
          )
        ), !0;
      case "gotpointercapture":
        return u = s.pointerId, Zl.set(
          u,
          Ql(
            Zl.get(u) || null,
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
  function Ly(t) {
    var e = Ea(t.target);
    if (e !== null) {
      var n = h(e);
      if (n !== null) {
        if (e = n.tag, e === 13) {
          if (e = d(n), e !== null) {
            t.blockedOn = e, wd(t.priority, function() {
              jy(n);
            });
            return;
          }
        } else if (e === 31) {
          if (e = p(n), e !== null) {
            t.blockedOn = e, wd(t.priority, function() {
              jy(n);
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
  function _u(t) {
    if (t.blockedOn !== null) return !1;
    for (var e = t.targetContainers; 0 < e.length; ) {
      var n = Qc(t.nativeEvent);
      if (n === null) {
        n = t.nativeEvent;
        var a = new n.constructor(
          n.type,
          n
        );
        No = a, n.target.dispatchEvent(a), No = null;
      } else
        return e = ei(n), e !== null && Vy(e), t.blockedOn = n, !1;
      e.shift();
    }
    return !0;
  }
  function Hy(t, e, n) {
    _u(t) && n.delete(e);
  }
  function IS() {
    Jc = !1, fa !== null && _u(fa) && (fa = null), da !== null && _u(da) && (da = null), ha !== null && _u(ha) && (ha = null), Xl.forEach(Hy), Zl.forEach(Hy);
  }
  function Vu(t, e) {
    t.blockedOn === e && (t.blockedOn = null, Jc || (Jc = !0, i.unstable_scheduleCallback(
      i.unstable_NormalPriority,
      IS
    )));
  }
  var ju = null;
  function Yy(t) {
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
    fa !== null && Vu(fa, t), da !== null && Vu(da, t), ha !== null && Vu(ha, t), Xl.forEach(e), Zl.forEach(e);
    for (var n = 0; n < ma.length; n++) {
      var a = ma[n];
      a.blockedOn === t && (a.blockedOn = null);
    }
    for (; 0 < ma.length && (n = ma[0], n.blockedOn === null); )
      Ly(n), n.blockedOn === null && ma.shift();
    if (n = (t.ownerDocument || t).$$reactFormReplay, n != null)
      for (a = 0; a < n.length; a += 3) {
        var s = n[a], u = n[a + 1], f = s[Te] || null;
        if (typeof u == "function")
          f || Yy(n);
        else if (f) {
          var m = null;
          if (u && u.hasAttribute("formAction")) {
            if (s = u, f = u[Te] || null)
              m = f.formAction;
            else if (Kc(s) !== null) continue;
          } else m = f.action;
          typeof m == "function" ? n[a + 1] = m : (n.splice(a, 3), a -= 3), Yy(n);
        }
      }
  }
  function qy() {
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
    zy(n, a, t, e, null, null);
  }, Uu.prototype.unmount = kc.prototype.unmount = function() {
    var t = this._internalRoot;
    if (t !== null) {
      this._internalRoot = null;
      var e = t.containerInfo;
      zy(t.current, 2, null, t, null, null), Su(), e[ti] = null;
    }
  };
  function Uu(t) {
    this._internalRoot = t;
  }
  Uu.prototype.unstable_scheduleHydration = function(t) {
    if (t) {
      var e = Nd();
      t = { blockedOn: null, target: t, priority: e };
      for (var n = 0; n < ma.length && e !== 0 && e < ma[n].priority; n++) ;
      ma.splice(n, 0, t), n === 0 && Ly(t);
    }
  };
  var Gy = l.version;
  if (Gy !== "19.3.1")
    throw Error(
      o(
        527,
        Gy,
        "19.3.1"
      )
    );
  st.findDOMNode = function(t) {
    var e = t._reactInternals;
    if (e === void 0)
      throw typeof t.render == "function" ? Error(o(188)) : (t = Object.keys(t).join(","), Error(o(268, t)));
    return t = b(e), t = t !== null ? g(t) : null, t = t === null ? null : t.stateNode, t;
  };
  var $S = {
    bundleType: 0,
    version: "19.3.1",
    rendererPackageName: "react-dom",
    currentDispatcherRef: I,
    reconcilerVersion: "19.3.1"
  };
  if (typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u") {
    var Bu = __REACT_DEVTOOLS_GLOBAL_HOOK__;
    if (!Bu.isDisabled && Bu.supportsFiber)
      try {
        $i = Bu.inject(
          $S
        ), Oe = Bu;
      } catch {
      }
  }
  return Jl.createRoot = function(t, e) {
    if (!c(t)) throw Error(o(299));
    var n = !1, a = "", s = Rm, u = zm, f = _m;
    return e != null && (e.unstable_strictMode === !0 && (n = !0), e.identifierPrefix !== void 0 && (a = e.identifierPrefix), e.onUncaughtError !== void 0 && (s = e.onUncaughtError), e.onCaughtError !== void 0 && (u = e.onCaughtError), e.onRecoverableError !== void 0 && (f = e.onRecoverableError)), e = wy(
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
      qy
    ), t[ti] = e.current, Ac(t), new kc(e);
  }, Jl.hydrateRoot = function(t, e, n) {
    if (!c(t)) throw Error(o(299));
    var a = !1, s = "", u = Rm, f = zm, m = _m, S = null;
    return n != null && (n.unstable_strictMode === !0 && (a = !0), n.identifierPrefix !== void 0 && (s = n.identifierPrefix), n.onUncaughtError !== void 0 && (u = n.onUncaughtError), n.onCaughtError !== void 0 && (f = n.onCaughtError), n.onRecoverableError !== void 0 && (m = n.onRecoverableError), n.formState !== void 0 && (S = n.formState)), e = wy(
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
      qy
    ), e.context = Ry(null), n = e.current, a = Ue(), a = Eo(a), s = In(a), s.callback = null, $n(n, s, a), n = a, e.current.lanes = n, el(e, n), bn(e), t[ti] = e.current, Ac(t), new Uu(e);
  }, Jl.version = "19.3.1", Jl;
}
var Iy;
function fT() {
  if (Iy) return Wc.exports;
  Iy = 1;
  function i() {
    if (!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" || typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function"))
      try {
        __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(i);
      } catch (l) {
        console.error(l);
      }
  }
  return i(), Wc.exports = cT(), Wc.exports;
}
var dT = fT();
const gg = K.createContext({});
function hT(i) {
  const l = K.useRef(null);
  return l.current === null && (l.current = i()), l.current;
}
const mT = typeof window < "u", pT = mT ? K.useLayoutEffect : K.useEffect, Kf = /* @__PURE__ */ K.createContext(null);
function Jf(i, l) {
  i.indexOf(l) === -1 && i.push(l);
}
function Fu(i, l) {
  const r = i.indexOf(l);
  r > -1 && i.splice(r, 1);
}
const En = (i, l, r) => r > l ? l : r < i ? i : r;
let oo = () => {
};
const ga = {}, vg = (i) => /^-?(?:\d+(?:\.\d+)?|\.\d+)$/u.test(i), bg = (i) => typeof i == "object" && i !== null, Sg = (i) => /^0[^.\s]+$/u.test(i);
// @__NO_SIDE_EFFECTS__
function Tg(i) {
  let l;
  return () => (l === void 0 && (l = i()), l);
}
const Pe = /* @__NO_SIDE_EFFECTS__ */ (i) => i, is = (...i) => i.reduce((l, r) => (o) => r(l(o))), ts = /* @__NO_SIDE_EFFECTS__ */ (i, l, r) => {
  const o = l - i;
  return o ? (r - i) / o : 1;
};
class kf {
  constructor() {
    this.subscriptions = [];
  }
  add(l) {
    return Jf(this.subscriptions, l), () => Fu(this.subscriptions, l);
  }
  notify(l, r, o) {
    const c = this.subscriptions.length;
    if (c)
      if (c === 1)
        this.subscriptions[0](l, r, o);
      else
        for (let h = 0; h < c; h++) {
          const d = this.subscriptions[h];
          d && d(l, r, o);
        }
  }
  getSize() {
    return this.subscriptions.length;
  }
  clear() {
    this.subscriptions.length = 0;
  }
}
const Le = /* @__NO_SIDE_EFFECTS__ */ (i) => i * 1e3, ke = /* @__NO_SIDE_EFFECTS__ */ (i) => i / 1e3, xg = /* @__NO_SIDE_EFFECTS__ */ (i, l) => l ? i * (1e3 / l) : 0, Eg = (i, l, r) => (((1 - 3 * r + 3 * l) * i + (3 * r - 6 * l)) * i + 3 * l) * i, yT = 1e-7, gT = 12;
function vT(i, l, r, o, c) {
  let h, d, p = 0;
  do
    d = l + (r - l) / 2, h = Eg(d, o, c) - i, h > 0 ? r = d : l = d;
  while (Math.abs(h) > yT && ++p < gT);
  return d;
}
// @__NO_SIDE_EFFECTS__
function ls(i, l, r, o) {
  if (i === l && r === o)
    return Pe;
  const c = (h) => vT(h, 0, 1, i, r);
  return (h) => h === 0 || h === 1 ? h : Eg(c(h), l, o);
}
const Ag = /* @__NO_SIDE_EFFECTS__ */ (i) => (l) => l <= 0.5 ? i(2 * l) / 2 : (2 - i(2 * (1 - l))) / 2, Mg = /* @__NO_SIDE_EFFECTS__ */ (i) => (l) => 1 - i(1 - l), Cg = /* @__PURE__ */ ls(0.33, 1.53, 0.69, 0.99), Pf = /* @__PURE__ */ Mg(Cg), Dg = /* @__PURE__ */ Ag(Pf), Og = (i) => i >= 1 ? 1 : (i *= 2) < 1 ? 0.5 * Pf(i) : 0.5 * (2 - Math.pow(2, -10 * (i - 1))), Ff = (i) => 1 - Math.sin(Math.acos(i)), Ng = /* @__PURE__ */ Mg(Ff), wg = /* @__PURE__ */ Ag(Ff), bT = /* @__PURE__ */ ls(0.42, 0, 1, 1), ST = /* @__PURE__ */ ls(0, 0, 0.58, 1), Rg = /* @__PURE__ */ ls(0.42, 0, 0.58, 1), TT = /* @__NO_SIDE_EFFECTS__ */ (i) => Array.isArray(i) && typeof i[0] != "number", zg = /* @__NO_SIDE_EFFECTS__ */ (i) => Array.isArray(i) && typeof i[0] == "number", xT = {
  linear: Pe,
  easeIn: bT,
  easeInOut: Rg,
  easeOut: ST,
  circIn: Ff,
  circInOut: wg,
  circOut: Ng,
  backIn: Pf,
  backInOut: Dg,
  backOut: Cg,
  anticipate: Og
}, ET = (i) => typeof i == "string", $y = (i) => {
  if (/* @__PURE__ */ zg(i)) {
    oo(i.length === 4);
    const [l, r, o, c] = i;
    return /* @__PURE__ */ ls(l, r, o, c);
  } else if (ET(i))
    return xT[i];
  return i;
}, Lu = [
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
function AT(i) {
  let l = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), o = !1, c = !1;
  const h = /* @__PURE__ */ new WeakSet();
  let d = {
    delta: 0,
    timestamp: 0,
    isProcessing: !1
  };
  function p(b) {
    h.has(b) && (v.schedule(b), i()), b(d);
  }
  const v = {
    /**
     * Schedule a process to run on the next frame.
     */
    schedule: (b, g = !1, y = !1) => {
      const V = y && o ? l : r;
      return g && h.add(b), V.add(b), b;
    },
    /**
     * Cancel the provided callback from running on the next frame.
     */
    cancel: (b) => {
      r.delete(b), h.delete(b);
    },
    /**
     * Execute all schedule callbacks.
     */
    process: (b) => {
      if (d = b, o) {
        c = !0;
        return;
      }
      o = !0;
      const g = l;
      l = r, r = g, l.forEach(p), l.clear(), o = !1, c && (c = !1, v.process(b));
    }
  };
  return v;
}
const MT = 40;
function _g(i, l) {
  let r = !1, o = !0;
  const c = {
    delta: 0,
    timestamp: 0,
    isProcessing: !1
  }, h = () => r = !0, d = Lu.reduce((X, Q) => (X[Q] = AT(h), X), {}), { setup: p, read: v, resolveKeyframes: b, preUpdate: g, update: y, preRender: T, render: V, postRender: R } = d, U = () => {
    const X = ga.useManualTiming, Q = X ? c.timestamp : performance.now();
    r = !1, X || (c.delta = o ? 1e3 / 60 : Math.max(Math.min(Q - c.timestamp, MT), 1)), c.timestamp = Q, c.isProcessing = !0, p.process(c), v.process(c), b.process(c), g.process(c), y.process(c), T.process(c), V.process(c), R.process(c), c.isProcessing = !1, r && l && (o = !1, i(U));
  }, j = () => {
    r = !0, o = !0, c.isProcessing || i(U);
  };
  return { schedule: Lu.reduce((X, Q) => {
    const it = d[Q];
    return X[Q] = (dt, J = !1, Z = !1) => (r || j(), it.schedule(dt, J, Z)), X;
  }, {}), cancel: (X) => {
    for (let Q = 0; Q < Lu.length; Q++)
      d[Lu[Q]].cancel(X);
  }, state: c, steps: d };
}
const { schedule: Vt, cancel: va, state: de, steps: ef } = /* @__PURE__ */ _g(typeof requestAnimationFrame < "u" ? requestAnimationFrame : Pe, !0);
let Gu;
function CT() {
  Gu = void 0;
}
const be = {
  now: () => (Gu === void 0 && be.set(de.isProcessing || ga.useManualTiming ? de.timestamp : performance.now()), Gu),
  set: (i) => {
    Gu = i, queueMicrotask(CT);
  }
}, Vg = (i) => (l) => typeof l == "string" && l.startsWith(i), jg = /* @__PURE__ */ Vg("--"), DT = /* @__PURE__ */ Vg("var(--"), Wf = (i) => DT(i) ? OT.test(i.split("/*")[0].trim()) : !1, OT = /var\(--(?:[\w-]+\s*|[\w-]+\s*,(?:\s*[^)(\s]|\s*\((?:[^)(]|\([^)(]*\))*\))+\s*)\)$/iu;
function t0(i) {
  return typeof i != "string" ? !1 : i.split("/*")[0].includes("var(--");
}
const Pi = {
  test: (i) => typeof i == "number",
  parse: parseFloat,
  transform: (i) => i
}, es = {
  ...Pi,
  transform: (i) => En(0, 1, i)
}, Hu = {
  ...Pi,
  default: 1
}, Fl = (i) => Math.round(i * 1e5) / 1e5, If = /-?(?:\d+(?:\.\d+)?|\.\d+)/gu;
function NT(i) {
  return i == null;
}
const wT = /^(?:#[\da-f]{3,8}|(?:rgb|hsl)a?\((?:-?[\d.]+%?[,\s]+){2}-?[\d.]+%?\s*(?:[,/]\s*)?(?:\b\d+(?:\.\d+)?|\.\d+)?%?\))$/iu, $f = (i, l) => (r) => !!(typeof r == "string" && wT.test(r) && r.startsWith(i) || l && !NT(r) && Object.prototype.hasOwnProperty.call(r, l)), Ug = (i, l, r) => (o) => {
  if (typeof o != "string")
    return o;
  const [c, h, d, p] = o.match(If);
  return {
    [i]: parseFloat(c),
    [l]: parseFloat(h),
    [r]: parseFloat(d),
    alpha: p !== void 0 ? parseFloat(p) : 1
  };
}, RT = (i) => En(0, 255, i), nf = {
  ...Pi,
  transform: (i) => Math.round(RT(i))
}, ka = {
  test: /* @__PURE__ */ $f("rgb", "red"),
  parse: /* @__PURE__ */ Ug("red", "green", "blue"),
  transform: ({ red: i, green: l, blue: r, alpha: o = 1 }) => "rgba(" + nf.transform(i) + ", " + nf.transform(l) + ", " + nf.transform(r) + ", " + Fl(es.transform(o)) + ")"
};
function zT(i) {
  let l = "", r = "", o = "", c = "";
  return i.length > 5 ? (l = i.substring(1, 3), r = i.substring(3, 5), o = i.substring(5, 7), c = i.substring(7, 9)) : (l = i.substring(1, 2), r = i.substring(2, 3), o = i.substring(3, 4), c = i.substring(4, 5), l += l, r += r, o += o, c += c), {
    red: parseInt(l, 16),
    green: parseInt(r, 16),
    blue: parseInt(o, 16),
    alpha: c ? parseInt(c, 16) / 255 : 1
  };
}
const Sf = {
  test: /* @__PURE__ */ $f("#"),
  parse: zT,
  transform: ka.transform
}, ss = /* @__NO_SIDE_EFFECTS__ */ (i) => ({
  test: (l) => typeof l == "string" && l.endsWith(i) && l.split(" ").length === 1,
  parse: parseFloat,
  transform: (l) => `${l}${i}`
}), Yn = /* @__PURE__ */ ss("deg"), xn = /* @__PURE__ */ ss("%"), F = /* @__PURE__ */ ss("px"), _T = /* @__PURE__ */ ss("vh"), VT = /* @__PURE__ */ ss("vw"), e0 = {
  ...xn,
  parse: (i) => xn.parse(i) / 100,
  transform: (i) => xn.transform(i * 100)
}, Zi = {
  test: /* @__PURE__ */ $f("hsl", "hue"),
  parse: /* @__PURE__ */ Ug("hue", "saturation", "lightness"),
  transform: ({ hue: i, saturation: l, lightness: r, alpha: o = 1 }) => "hsla(" + Math.round(i) + ", " + xn.transform(Fl(l)) + ", " + xn.transform(Fl(r)) + ", " + Fl(es.transform(o)) + ")"
}, Ft = {
  test: (i) => ka.test(i) || Sf.test(i) || Zi.test(i),
  parse: (i) => ka.test(i) ? ka.parse(i) : Zi.test(i) ? Zi.parse(i) : Sf.parse(i),
  transform: (i) => typeof i == "string" ? i : i.hasOwnProperty("red") ? ka.transform(i) : Zi.transform(i),
  getAnimatableNone: (i) => {
    const l = Ft.parse(i);
    return l.alpha = 0, Ft.transform(l);
  }
}, jT = /(?:#[\da-f]{3,8}|(?:rgb|hsl)a?\((?:-?[\d.]+%?[,\s]+){2}-?[\d.]+%?\s*(?:[,/]\s*)?(?:\b\d+(?:\.\d+)?|\.\d+)?%?\))/giu;
function UT(i) {
  return isNaN(i) && typeof i == "string" && (i.match(If)?.length || 0) + (i.match(jT)?.length || 0) > 0;
}
const Bg = "number", Lg = "color", BT = "var", LT = "var(", n0 = "${}", HT = /var\s*\(\s*--(?:[\w-]+\s*|[\w-]+\s*,(?:\s*[^)(\s]|\s*\((?:[^)(]|\([^)(]*\))*\))+\s*)\)|#[\da-f]{3,8}|(?:rgb|hsl)a?\((?:-?[\d.]+%?[,\s]+){2}-?[\d.]+%?\s*(?:[,/]\s*)?(?:\b\d+(?:\.\d+)?|\.\d+)?%?\)|-?(?:\d+(?:\.\d+)?|\.\d+)/giu;
function Ji(i) {
  const l = i.toString(), r = [], o = {
    color: [],
    number: [],
    var: []
  }, c = [];
  let h = 0;
  const p = l.replace(HT, (v) => (Ft.test(v) ? (o.color.push(h), c.push(Lg), r.push(Ft.parse(v))) : v.startsWith(LT) ? (o.var.push(h), c.push(BT), r.push(v)) : (o.number.push(h), c.push(Bg), r.push(parseFloat(v))), ++h, n0)).split(n0);
  return { values: r, split: p, indexes: o, types: c };
}
function YT(i) {
  return Ji(i).values;
}
function Hg({ split: i, types: l }) {
  const r = i.length;
  return (o) => {
    let c = "";
    for (let h = 0; h < r; h++)
      if (c += i[h], o[h] !== void 0) {
        const d = l[h];
        d === Bg ? c += Fl(o[h]) : d === Lg ? c += Ft.transform(o[h]) : c += o[h];
      }
    return c;
  };
}
function qT(i) {
  return Hg(Ji(i));
}
const GT = (i) => typeof i == "number" ? 0 : Ft.test(i) ? Ft.getAnimatableNone(i) : i, XT = (i, l) => typeof i == "number" ? l?.trim().endsWith("/") ? i : 0 : GT(i);
function ZT(i) {
  const l = Ji(i);
  return Hg(l)(l.values.map((o, c) => XT(o, l.split[c])));
}
const sn = {
  test: UT,
  parse: YT,
  createTransformer: qT,
  getAnimatableNone: ZT
};
function af(i, l, r) {
  return r < 0 && (r += 1), r > 1 && (r -= 1), r < 1 / 6 ? i + (l - i) * 6 * r : r < 1 / 2 ? l : r < 2 / 3 ? i + (l - i) * (2 / 3 - r) * 6 : i;
}
function QT({ hue: i, saturation: l, lightness: r, alpha: o }) {
  i /= 360, l /= 100, r /= 100;
  let c = 0, h = 0, d = 0;
  if (!l)
    c = h = d = r;
  else {
    const p = r < 0.5 ? r * (1 + l) : r + l - r * l, v = 2 * r - p;
    c = af(v, p, i + 1 / 3), h = af(v, p, i), d = af(v, p, i - 1 / 3);
  }
  return {
    red: Math.round(c * 255),
    green: Math.round(h * 255),
    blue: Math.round(d * 255),
    alpha: o
  };
}
function Wu(i, l) {
  return (r) => r > 0 ? l : i;
}
const _t = (i, l, r) => i + (l - i) * r, lf = (i, l, r) => {
  const o = i * i, c = r * (l * l - o) + o;
  return c < 0 ? 0 : Math.sqrt(c);
}, KT = [Sf, ka, Zi], JT = (i) => KT.find((l) => l.test(i));
function a0(i) {
  const l = JT(i);
  if (!l)
    return !1;
  let r = l.parse(i);
  return l === Zi && (r = QT(r)), r;
}
const i0 = (i, l) => {
  const r = a0(i), o = a0(l);
  if (!r || !o)
    return Wu(i, l);
  const c = { ...r };
  return (h) => (c.red = lf(r.red, o.red, h), c.green = lf(r.green, o.green, h), c.blue = lf(r.blue, o.blue, h), c.alpha = _t(r.alpha, o.alpha, h), ka.transform(c));
}, Tf = /* @__PURE__ */ new Set(["none", "hidden"]);
function kT(i, l) {
  return Tf.has(i) ? (r) => r <= 0 ? i : l : (r) => r >= 1 ? l : i;
}
function PT(i, l) {
  return (r) => _t(i, l, r);
}
function td(i) {
  return typeof i == "number" ? PT : typeof i == "string" ? Wf(i) ? Wu : Ft.test(i) ? i0 : IT : Array.isArray(i) ? Yg : typeof i == "object" ? Ft.test(i) ? i0 : FT : Wu;
}
function Yg(i, l) {
  const r = [...i], o = r.length, c = i.map((h, d) => td(h)(h, l[d]));
  return (h) => {
    for (let d = 0; d < o; d++)
      r[d] = c[d](h);
    return r;
  };
}
function FT(i, l) {
  const r = { ...i, ...l }, o = {};
  for (const c in r)
    i[c] !== void 0 && l[c] !== void 0 && (o[c] = td(i[c])(i[c], l[c]));
  return (c) => {
    for (const h in o)
      r[h] = o[h](c);
    return r;
  };
}
function WT(i, l) {
  const r = [], o = { color: 0, var: 0, number: 0 };
  for (let c = 0; c < l.values.length; c++) {
    const h = l.types[c], d = i.indexes[h][o[h]], p = i.values[d] ?? 0;
    r[c] = p, o[h]++;
  }
  return r;
}
const IT = (i, l) => {
  const r = sn.createTransformer(l), o = Ji(i), c = Ji(l);
  return o.indexes.var.length === c.indexes.var.length && o.indexes.color.length === c.indexes.color.length && o.indexes.number.length >= c.indexes.number.length ? Tf.has(i) && !c.values.length || Tf.has(l) && !o.values.length ? kT(i, l) : is(Yg(WT(o, c), c.values), r) : Wu(i, l);
};
function qg(i, l, r) {
  return typeof i == "number" && typeof l == "number" && typeof r == "number" ? _t(i, l, r) : td(i)(i, l);
}
const $T = (i) => {
  const l = ({ timestamp: r }) => i(r);
  return {
    start: (r = !0) => Vt.update(l, r),
    stop: () => va(l),
    /**
     * If we're processing this frame we can use the
     * framelocked timestamp to keep things in sync.
     */
    now: () => de.isProcessing ? de.timestamp : be.now()
  };
}, Gg = (i, l, r = 10) => {
  let o = "";
  const c = Math.max(Math.round(l / r), 2);
  for (let h = 0; h < c; h++)
    o += Math.round(i(h / (c - 1)) * 1e4) / 1e4 + ", ";
  return `linear(${o.substring(0, o.length - 2)})`;
}, Iu = 2e4;
function ed(i) {
  let l = 0;
  const r = 50;
  let o = i.next(l);
  for (; !o.done && l < Iu; )
    l += r, o = i.next(l);
  return l >= Iu ? 1 / 0 : l;
}
function tx(i, l = 100, r) {
  const o = r({ ...i, keyframes: [0, l] }), c = Math.min(ed(o), Iu);
  return {
    type: "keyframes",
    ease: (h) => o.next(c * h).value / l,
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
const ex = 12;
function nx(i, l, r) {
  let o = r;
  for (let c = 1; c < ex; c++)
    o = o - i(o) / l(o);
  return o;
}
const sf = 1e-3;
function ax({ duration: i = Gt.duration, bounce: l = Gt.bounce, velocity: r = Gt.velocity, mass: o = Gt.mass }) {
  let c, h, d = 1 - l;
  d = En(Gt.minDamping, Gt.maxDamping, d), i = En(Gt.minDuration, Gt.maxDuration, /* @__PURE__ */ ke(i)), d < 1 ? (c = (b) => {
    const g = b * d, y = g * i, T = g - r, V = xf(b, d), R = Math.exp(-y);
    return sf - T / V * R;
  }, h = (b) => {
    const y = b * d * i, T = y * r + r, V = Math.pow(d, 2) * Math.pow(b, 2) * i, R = Math.exp(-y), U = xf(Math.pow(b, 2), d);
    return (-c(b) + sf > 0 ? -1 : 1) * ((T - V) * R) / U;
  }) : (c = (b) => {
    const g = Math.exp(-b * i), y = (b - r) * i + 1;
    return -sf + g * y;
  }, h = (b) => {
    const g = Math.exp(-b * i), y = (r - b) * (i * i);
    return g * y;
  });
  const p = 5 / i, v = nx(c, h, p);
  if (i = /* @__PURE__ */ Le(i), isNaN(v))
    return {
      stiffness: Gt.stiffness,
      damping: Gt.damping,
      duration: i
    };
  {
    const b = Math.pow(v, 2) * o;
    return {
      stiffness: b,
      damping: d * 2 * Math.sqrt(o * b),
      duration: i
    };
  }
}
const ix = ["duration", "bounce"], lx = ["stiffness", "damping", "mass"];
function l0(i, l) {
  return l.some((r) => i[r] !== void 0);
}
function sx(i) {
  let l = {
    velocity: Gt.velocity,
    stiffness: Gt.stiffness,
    damping: Gt.damping,
    mass: Gt.mass,
    isResolvedFromDuration: !1,
    ...i
  };
  if (!l0(i, lx) && l0(i, ix))
    if (l.velocity = 0, i.visualDuration) {
      const r = i.visualDuration, o = 2 * Math.PI / (r * 1.2), c = o * o, h = 2 * En(0.05, 1, 1 - (i.bounce || 0)) * Math.sqrt(c);
      l = {
        ...l,
        mass: Gt.mass,
        stiffness: c,
        damping: h
      };
    } else {
      const r = ax({ ...i, velocity: 0 });
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
  const h = r.keyframes[0], d = r.keyframes[r.keyframes.length - 1], p = { done: !1, value: h }, { stiffness: v, damping: b, mass: g, duration: y, velocity: T, isResolvedFromDuration: V } = sx({
    ...r,
    velocity: -/* @__PURE__ */ ke(r.velocity || 0)
  }), R = T || 0, U = b / (2 * Math.sqrt(v * g)), j = d - h, H = /* @__PURE__ */ ke(Math.sqrt(v / g)), q = Math.abs(j) < 5;
  o || (o = q ? Gt.restSpeed.granular : Gt.restSpeed.default), c || (c = q ? Gt.restDelta.granular : Gt.restDelta.default);
  let X, Q, it, dt, J, Z;
  if (U < 1)
    it = xf(H, U), dt = (R + U * H * j) / it, X = (W) => {
      const yt = Math.exp(-U * H * W);
      return d - yt * (dt * Math.sin(it * W) + j * Math.cos(it * W));
    }, J = U * H * dt + j * it, Z = U * H * j - dt * it, Q = (W) => Math.exp(-U * H * W) * (J * Math.sin(it * W) + Z * Math.cos(it * W));
  else if (U === 1) {
    X = (yt) => d - Math.exp(-H * yt) * (j + (R + H * j) * yt);
    const W = R + H * j;
    Q = (yt) => Math.exp(-H * yt) * (H * W * yt - R);
  } else {
    const W = H * Math.sqrt(U * U - 1);
    X = (Zt) => {
      const Ct = Math.exp(-U * H * Zt), Y = Math.min(W * Zt, 300);
      return d - Ct * ((R + U * H * j) * Math.sinh(Y) + W * j * Math.cosh(Y)) / W;
    };
    const yt = (R + U * H * j) / W, ot = U * H * yt - j * W, $t = U * H * j - yt * W;
    Q = (Zt) => {
      const Ct = Math.exp(-U * H * Zt), Y = Math.min(W * Zt, 300);
      return Ct * (ot * Math.sinh(Y) + $t * Math.cosh(Y));
    };
  }
  const Mt = {
    calculatedDuration: V && y || null,
    velocity: (W) => /* @__PURE__ */ Le(Q(W)),
    next: (W) => {
      if (!V && U < 1) {
        const ot = Math.exp(-U * H * W), $t = Math.sin(it * W), Zt = Math.cos(it * W), Ct = d - ot * (dt * $t + j * Zt), Y = /* @__PURE__ */ Le(ot * (J * $t + Z * Zt));
        return p.done = Math.abs(Y) <= o && Math.abs(d - Ct) <= c, p.value = p.done ? d : Ct, p;
      }
      const yt = X(W);
      if (V)
        p.done = W >= y;
      else {
        const ot = /* @__PURE__ */ Le(Q(W));
        p.done = Math.abs(ot) <= o && Math.abs(d - yt) <= c;
      }
      return p.value = p.done ? d : yt, p;
    },
    toString: () => {
      const W = Math.min(ed(Mt), Iu), yt = Gg((ot) => Mt.next(W * ot).value, W, 30);
      return W + "ms " + yt;
    },
    toTransition: () => {
    }
  };
  return Mt;
}
$u.applyToOptions = (i) => {
  const l = tx(i, 100, $u);
  return i.ease = l.ease, i.duration = /* @__PURE__ */ Le(l.duration), i.type = "keyframes", i;
};
const ux = 5;
function Xg(i, l, r) {
  const o = Math.max(l - ux, 0);
  return /* @__PURE__ */ xg(r - i(o), l - o);
}
function Ef({ keyframes: i, velocity: l = 0, power: r = 0.8, timeConstant: o = 325, bounceDamping: c = 10, bounceStiffness: h = 500, modifyTarget: d, min: p, max: v, restDelta: b = 0.5, restSpeed: g }) {
  const y = i[0], T = {
    done: !1,
    value: y
  }, V = (Z) => p !== void 0 && Z < p || v !== void 0 && Z > v, R = (Z) => p === void 0 ? v : v === void 0 || Math.abs(p - Z) < Math.abs(v - Z) ? p : v;
  let U = r * l;
  const j = y + U, H = d === void 0 ? j : d(j);
  H !== j && (U = H - y);
  const q = (Z) => -U * Math.exp(-Z / o), X = (Z) => H + q(Z), Q = (Z) => {
    const Mt = q(Z), W = X(Z);
    T.done = Math.abs(Mt) <= b, T.value = T.done ? H : W;
  };
  let it, dt;
  const J = (Z) => {
    V(T.value) && (it = Z, dt = $u({
      keyframes: [T.value, R(T.value)],
      velocity: Xg(X, Z, T.value),
      // TODO: This should be passing * 1000
      damping: c,
      stiffness: h,
      restDelta: b,
      restSpeed: g
    }));
  };
  return J(0), {
    calculatedDuration: null,
    next: (Z) => {
      let Mt = !1;
      return !dt && it === void 0 && (Mt = !0, Q(Z), J(Z)), it !== void 0 && Z >= it ? dt.next(Z - it) : (!Mt && Q(Z), T);
    }
  };
}
function ox(i, l, r) {
  const o = [], c = r || ga.mix || qg, h = i.length - 1;
  for (let d = 0; d < h; d++) {
    let p = c(i[d], i[d + 1]);
    if (l) {
      const v = Array.isArray(l) ? l[d] || Pe : l;
      p = is(v, p);
    }
    o.push(p);
  }
  return o;
}
function rx(i, l, { clamp: r = !0, ease: o, mixer: c } = {}) {
  const h = i.length;
  if (oo(h === l.length), h === 1)
    return () => l[0];
  if (h === 2 && l[0] === l[1])
    return () => l[1];
  const d = i[0] === i[1];
  i[0] > i[h - 1] && (i = [...i].reverse(), l = [...l].reverse());
  const p = ox(l, o, c), v = p.length, b = (g) => {
    if (d && g < i[0])
      return l[0];
    let y = 0;
    if (v > 1)
      for (; y < i.length - 2 && !(g < i[y + 1]); y++)
        ;
    const T = /* @__PURE__ */ ts(i[y], i[y + 1], g);
    return p[y](T);
  };
  return r ? (g) => b(En(i[0], i[h - 1], g)) : b;
}
function cx(i, l) {
  const r = i[i.length - 1];
  for (let o = 1; o <= l; o++) {
    const c = /* @__PURE__ */ ts(0, l, o);
    i.push(_t(r, 1, c));
  }
}
function fx(i) {
  const l = [0];
  return cx(l, i.length - 1), l;
}
function dx(i, l) {
  return i.map((r) => r * l);
}
function hx(i, l) {
  return i.map(() => l || Rg).splice(0, i.length - 1);
}
function Wl({ duration: i = 300, keyframes: l, times: r, ease: o = "easeInOut" }) {
  const c = /* @__PURE__ */ TT(o) ? o.map($y) : $y(o), h = {
    done: !1,
    value: l[0]
  }, d = dx(
    // Only use the provided offsets if they're the correct length
    // TODO Maybe we should warn here if there's a length mismatch
    r && r.length === l.length ? r : fx(l),
    i
  ), p = rx(d, l, {
    ease: Array.isArray(c) ? c : hx(l, c)
  });
  return {
    calculatedDuration: i,
    next: (v) => (h.value = p(v), h.done = v >= i, h)
  };
}
const mx = (i) => i !== null;
function ro(i, { repeat: l, repeatType: r = "loop" }, o, c = 1) {
  const h = i.filter(mx), p = c < 0 || l && r !== "loop" && l % 2 === 1 ? 0 : h.length - 1;
  return !p || o === void 0 ? h[p] : o;
}
const px = {
  decay: Ef,
  inertia: Ef,
  tween: Wl,
  keyframes: Wl,
  spring: $u
};
function Zg(i) {
  typeof i.type == "string" && (i.type = px[i.type]);
}
class nd {
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
const yx = (i) => i / 100;
class to extends nd {
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
    Zg(l);
    const { type: r = Wl, repeat: o = 0, repeatDelay: c = 0, repeatType: h, velocity: d = 0 } = l;
    let { keyframes: p } = l;
    const v = r || Wl;
    v !== Wl && typeof p[0] != "number" && (this.mixKeyframes = is(yx, qg(p[0], p[1])), p = [0, 100]);
    const b = v({ ...l, keyframes: p });
    h === "mirror" && (this.mirroredGenerator = v({
      ...l,
      keyframes: [...p].reverse(),
      velocity: -d
    })), b.calculatedDuration === null && (b.calculatedDuration = ed(b));
    const { calculatedDuration: g } = b;
    this.calculatedDuration = g, this.resolvedDuration = g + c, this.totalDuration = this.resolvedDuration * (o + 1) - c, this.generator = b;
  }
  updateTime(l) {
    const r = Math.round(l - this.startTime) * this.playbackSpeed;
    this.holdTime !== null ? this.currentTime = this.holdTime : this.currentTime = r;
  }
  tick(l, r = !1) {
    const { generator: o, totalDuration: c, mixKeyframes: h, mirroredGenerator: d, resolvedDuration: p, calculatedDuration: v } = this;
    if (this.startTime === null)
      return o.next(0);
    const { delay: b = 0, keyframes: g, repeat: y, repeatType: T, repeatDelay: V, type: R, onUpdate: U, finalKeyframe: j } = this.options;
    this.speed > 0 ? this.startTime = Math.min(this.startTime, l) : this.speed < 0 && (this.startTime = Math.min(l - c / this.speed, this.startTime)), r ? this.currentTime = l : this.updateTime(l);
    const H = this.currentTime - b * (this.playbackSpeed >= 0 ? 1 : -1), q = this.playbackSpeed >= 0 ? H < 0 : H > c;
    this.currentTime = Math.max(H, 0), this.state === "finished" && this.holdTime === null && (this.currentTime = c);
    let X = this.currentTime, Q = o;
    if (y) {
      const Z = Math.min(this.currentTime, c) / p;
      let Mt = Math.floor(Z), W = Z % 1;
      !W && Z >= 1 && (W = 1), W === 1 && Mt--, Mt = Math.min(Mt, y + 1), Mt % 2 && (T === "reverse" ? (W = 1 - W, V && (W -= V / p)) : T === "mirror" && (Q = d)), X = En(0, 1, W) * p;
    }
    let it;
    q ? (this.delayState.value = g[0], it = this.delayState) : it = Q.next(X), h && !q && (it.value = h(it.value));
    let { done: dt } = it;
    !q && v !== null && (dt = this.playbackSpeed >= 0 ? this.currentTime >= c : this.currentTime <= 0);
    const J = this.holdTime === null && (this.state === "finished" || this.state === "running" && dt);
    return J && R !== Ef && (it.value = ro(g, this.options, j, this.speed)), U && U(it.value), J && this.finish(), it;
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
    l = /* @__PURE__ */ Le(l), this.currentTime = l, this.startTime === null || this.holdTime !== null || this.playbackSpeed === 0 ? this.holdTime = l : this.driver && (this.startTime = this.driver.now() - l / this.playbackSpeed), this.driver ? this.driver.start(!1) : (this.startTime = 0, this.state = "paused", this.holdTime = l, this.tick(l));
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
    return Xg((o) => this.generator.next(o).value, l, r);
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
    const { driver: l = $T, startTime: r } = this.options;
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
function gx(i) {
  for (let l = 1; l < i.length; l++)
    i[l] ?? (i[l] = i[l - 1]);
}
const Pa = (i) => i * 180 / Math.PI, Af = (i) => {
  const l = Pa(Math.atan2(i[1], i[0]));
  return Mf(l);
}, vx = {
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
}, Mf = (i) => (i = i % 360, i < 0 && (i += 360), i), s0 = Af, u0 = (i) => Math.sqrt(i[0] * i[0] + i[1] * i[1]), o0 = (i) => Math.sqrt(i[4] * i[4] + i[5] * i[5]), bx = {
  x: 12,
  y: 13,
  z: 14,
  translateX: 12,
  translateY: 13,
  translateZ: 14,
  scaleX: u0,
  scaleY: o0,
  scale: (i) => (u0(i) + o0(i)) / 2,
  rotateX: (i) => Mf(Pa(Math.atan2(i[6], i[5]))),
  rotateY: (i) => Mf(Pa(Math.atan2(-i[2], i[0]))),
  rotateZ: s0,
  rotate: s0,
  skewX: (i) => Pa(Math.atan(i[4])),
  skewY: (i) => Pa(Math.atan(i[1])),
  skew: (i) => (Math.abs(i[1]) + Math.abs(i[4])) / 2
};
function Cf(i) {
  return i.includes("scale") ? 1 : 0;
}
function Df(i, l) {
  if (!i || i === "none")
    return Cf(l);
  const r = i.match(/^matrix3d\(([-\d.e\s,]+)\)$/u);
  let o, c;
  if (r)
    o = bx, c = r;
  else {
    const p = i.match(/^matrix\(([-\d.e\s,]+)\)$/u);
    o = vx, c = p;
  }
  if (!c)
    return Cf(l);
  const h = o[l], d = c[1].split(",").map(Tx);
  return typeof h == "function" ? h(d) : d[h];
}
const Sx = (i, l) => {
  const { transform: r = "none" } = getComputedStyle(i);
  return Df(r, l);
};
function Tx(i) {
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
], Wi = /* @__PURE__ */ new Set([...Fi, "pathRotation"]), r0 = (i) => i === Pi || i === F, xx = /* @__PURE__ */ new Set(["x", "y", "z"]), Ex = Fi.filter((i) => !xx.has(i));
function Ax(i) {
  const l = [];
  return Ex.forEach((r) => {
    const o = i.getValue(r);
    o !== void 0 && (l.push([r, o.get()]), o.set(r.startsWith("scale") ? 1 : 0));
  }), l;
}
const ya = {
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
  x: (i, { transform: l }) => Df(l, "x"),
  y: (i, { transform: l }) => Df(l, "y")
};
ya.translateX = ya.x;
ya.translateY = ya.y;
const Fa = /* @__PURE__ */ new Set();
let Of = !1, Nf = !1, wf = !1;
function Qg() {
  if (Nf) {
    const i = Array.from(Fa).filter((o) => o.needsMeasurement), l = new Set(i.map((o) => o.element)), r = /* @__PURE__ */ new Map();
    l.forEach((o) => {
      const c = Ax(o);
      c.length && (r.set(o, c), o.render());
    }), i.forEach((o) => o.measureInitialState()), l.forEach((o) => {
      o.render();
      const c = r.get(o);
      c && c.forEach(([h, d]) => {
        o.getValue(h)?.set(d);
      });
    }), i.forEach((o) => o.measureEndState()), i.forEach((o) => {
      o.suspendedScrollY !== void 0 && window.scrollTo(0, o.suspendedScrollY);
    });
  }
  Nf = !1, Of = !1, Fa.forEach((i) => i.complete(wf)), Fa.clear();
}
function Kg() {
  Fa.forEach((i) => {
    i.readKeyframes(), i.needsMeasurement && (Nf = !0);
  });
}
function Mx() {
  wf = !0, Kg(), Qg(), wf = !1;
}
class ad {
  constructor(l, r, o, c, h, d = !1) {
    this.state = "pending", this.isAsync = !1, this.needsMeasurement = !1, this.unresolvedKeyframes = [...l], this.onComplete = r, this.name = o, this.motionValue = c, this.element = h, this.isAsync = d;
  }
  scheduleResolve() {
    this.state = "scheduled", this.isAsync ? (Fa.add(this), Of || (Of = !0, Vt.read(Kg), Vt.resolveKeyframes(Qg))) : (this.readKeyframes(), this.complete());
  }
  readKeyframes() {
    const { unresolvedKeyframes: l, name: r, element: o, motionValue: c } = this;
    if (l[0] === null) {
      const h = c?.get(), d = l[l.length - 1];
      if (h !== void 0)
        l[0] = h;
      else if (o && r) {
        const p = o.readValue(r, d);
        p != null && (l[0] = p);
      }
      l[0] === void 0 && (l[0] = d), c && h === void 0 && c.set(l[0]);
    }
    gx(l);
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
function Jg(i, l, r) {
  Cx(l) ? i.style.setProperty(l, r) : i.style[l] = r;
}
const Dx = {};
function kg(i, l) {
  const r = /* @__PURE__ */ Tg(i);
  return () => Dx[l] ?? r();
}
const Ox = /* @__PURE__ */ kg(() => window.ScrollTimeline !== void 0, "scrollTimeline"), Pg = /* @__PURE__ */ kg(() => {
  try {
    document.createElement("div").animate({ opacity: 0 }, { easing: "linear(0, 1)" });
  } catch {
    return !1;
  }
  return !0;
}, "linearEasing"), Pl = ([i, l, r, o]) => `cubic-bezier(${i}, ${l}, ${r}, ${o})`, c0 = {
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
function Fg(i, l) {
  if (i)
    return typeof i == "function" ? Pg() ? Gg(i, l) : "ease-out" : /* @__PURE__ */ zg(i) ? Pl(i) : Array.isArray(i) ? i.map((r) => Fg(r, l) || c0.easeOut) : c0[i];
}
function Nx(i, l, r, { delay: o = 0, duration: c = 300, repeat: h = 0, repeatType: d = "loop", ease: p = "easeOut", times: v } = {}, b = void 0) {
  const g = {
    [l]: r
  };
  v && (g.offset = v);
  const y = Fg(p, c);
  Array.isArray(y) && (g.easing = y);
  const T = {
    delay: o,
    duration: c,
    easing: Array.isArray(y) ? "linear" : y,
    fill: "both",
    iterations: h + 1,
    direction: d === "reverse" ? "alternate" : "normal"
  };
  return b && (T.pseudoElement = b), i.animate(g, T);
}
function Wg(i) {
  return typeof i == "function" && "applyToOptions" in i;
}
function wx({ type: i, ...l }) {
  return Wg(i) && Pg() ? i.applyToOptions(l) : (l.duration ?? (l.duration = 300), l.ease ?? (l.ease = "easeOut"), l);
}
class Ig extends nd {
  constructor(l) {
    if (super(), this.finishedTime = null, this.isStopped = !1, this.manualStartTime = null, !l)
      return;
    const { element: r, name: o, keyframes: c, pseudoElement: h, allowFlatten: d = !1, finalKeyframe: p, onComplete: v } = l;
    this.isPseudoElement = !!h, this.allowFlatten = d, this.options = l, oo(typeof l.type != "string");
    const b = wx(l);
    this.animation = Nx(r, o, c, b, h), b.autoplay === !1 && this.animation.pause(), this.animation.onfinish = () => {
      if (this.finishedTime = this.time, !h) {
        const g = ro(c, this.options, p, this.speed);
        this.updateMotionValue && this.updateMotionValue(g), Jg(r, o, g), this.animation.cancel();
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
    this.manualStartTime = null, this.finishedTime = null, this.animation.currentTime = /* @__PURE__ */ Le(l), r && this.animation.pause();
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
    return this.allowFlatten && this.animation.effect?.updateTiming({ easing: "linear" }), this.animation.onfinish = null, l && Ox() ? (this.animation.timeline = l, r && (this.animation.rangeStart = r), o && (this.animation.rangeEnd = o), Pe) : c(this);
  }
}
const $g = {
  anticipate: Og,
  backInOut: Dg,
  circInOut: wg
};
function Rx(i) {
  return i in $g;
}
function zx(i) {
  typeof i.ease == "string" && Rx(i.ease) && (i.ease = $g[i.ease]);
}
const uf = 10;
class _x extends Ig {
  constructor(l) {
    zx(l), Zg(l), super(l), l.startTime !== void 0 && l.autoplay !== !1 && (this.startTime = l.startTime), this.options = l;
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
    const { motionValue: r, onUpdate: o, onComplete: c, element: h, ...d } = this.options;
    if (!r)
      return;
    if (l !== void 0) {
      r.set(l);
      return;
    }
    const p = new to({
      ...d,
      autoplay: !1
    }), v = Math.max(uf, be.now() - this.startTime), b = En(0, uf, v - uf), g = p.sample(v).value, { name: y } = this.options;
    h && y && Jg(h, y, g), r.setWithVelocity(p.sample(Math.max(0, v - b)).value, g, b), p.stop();
  }
}
const f0 = (i, l) => l === "zIndex" ? !1 : !!(typeof i == "number" || Array.isArray(i) || typeof i == "string" && // It's animatable if we have a string
(sn.test(i) || i === "0") && // And it contains numbers and/or colors
!i.startsWith("url("));
function Vx(i) {
  const l = i[0];
  if (i.length === 1)
    return !0;
  for (let r = 0; r < i.length; r++)
    if (i[r] !== l)
      return !0;
}
function jx(i, l, r, o) {
  const c = i[0];
  if (c === null)
    return !1;
  if (l === "display" || l === "visibility")
    return !0;
  const h = i[i.length - 1], d = f0(c, l), p = f0(h, l);
  return !d || !p ? !1 : Vx(i) || (r === "spring" || Wg(r)) && o;
}
function Rf(i) {
  i.duration = 0, i.type = "keyframes";
}
const tv = /* @__PURE__ */ new Set([
  "opacity",
  "clipPath",
  "filter",
  "transform",
  "backgroundColor"
]), Ux = /^(?:oklch|oklab|lab|lch|color|color-mix|light-dark)\(/;
function Bx(i) {
  for (let l = 0; l < i.length; l++)
    if (typeof i[l] == "string" && Ux.test(i[l]))
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
]), Hx = /* @__PURE__ */ Tg(() => Object.hasOwnProperty.call(Element.prototype, "animate"));
function Yx(i) {
  const { motionValue: l, name: r, repeatDelay: o, repeatType: c, damping: h, type: d, keyframes: p } = i, v = l?.owner?.current;
  if (!(v instanceof HTMLElement) && !(v instanceof SVGElement))
    return !1;
  const { onUpdate: b, transformTemplate: g } = l.owner.getProps();
  return Hx() && r && /**
   * Force WAAPI for color properties with browser-only color formats
   * (oklch, oklab, lab, lch, etc.) that the JS animation path can't parse.
   */
  (tv.has(r) || Lx.has(r) && Bx(p)) && (r !== "transform" || !g) && /**
   * If we're outputting values to onUpdate then we can't use WAAPI as there's
   * no way to read the value from WAAPI every frame.
   */
  !b && !o && c !== "mirror" && h !== 0 && d !== "inertia";
}
const qx = 40;
class Gx extends nd {
  constructor({ autoplay: l = !0, delay: r = 0, type: o = "keyframes", repeat: c = 0, repeatDelay: h = 0, repeatType: d = "loop", keyframes: p, name: v, motionValue: b, element: g, ...y }) {
    super(), this.stop = () => {
      this._animation && (this._animation.stop(), this.stopTimeline?.()), this.keyframeResolver?.cancel();
    }, this.createdAt = be.now();
    const T = {
      autoplay: l,
      delay: r,
      type: o,
      repeat: c,
      repeatDelay: h,
      repeatType: d,
      name: v,
      motionValue: b,
      element: g,
      ...y
    }, V = g?.KeyframeResolver || ad;
    this.keyframeResolver = new V(p, (R, U, j) => this.onKeyframesResolved(R, U, T, !j), v, b, g), this.keyframeResolver?.scheduleResolve();
  }
  onKeyframesResolved(l, r, o, c) {
    this.keyframeResolver = void 0;
    const { name: h, type: d, velocity: p, delay: v, isHandoff: b, onUpdate: g } = o;
    this.resolvedAt = be.now();
    let y = !0;
    jx(l, h, d, p) || (y = !1, (ga.instantAnimations || !v) && g?.(ro(l, o, r)), l[0] = l[l.length - 1], Rf(o), o.repeat = 0);
    const V = {
      startTime: c ? this.resolvedAt ? this.resolvedAt - this.createdAt > qx ? this.resolvedAt : this.createdAt : this.createdAt : void 0,
      finalKeyframe: r,
      ...o,
      keyframes: l
    }, R = y && !b && Yx(V), U = V.motionValue?.owner?.current;
    let j;
    if (R)
      try {
        j = new _x({
          ...V,
          element: U
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
    return this._animation || (this.keyframeResolver?.resume(), Mx()), this._animation;
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
function ev(i, l, r, o = 0, c = 1) {
  const h = Array.from(i).sort((b, g) => b.sortNodePosition(g)).indexOf(l), d = i.size, p = (d - 1) * o;
  return typeof r == "function" ? r(h, d) : c === 1 ? h * o : p - h * o;
}
const d0 = 30, Xx = (i) => !isNaN(parseFloat(i));
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
        for (const h of this.dependents)
          h.dirty();
    }, this.hasAnimated = !1, this.setCurrent(l), this.owner = r.owner;
  }
  setCurrent(l) {
    this.current = l, this.updatedAt = be.now(), this.canTrackVelocity === null && l !== void 0 && (this.canTrackVelocity = Xx(this.current));
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
    this.events[l] || (this.events[l] = new kf());
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
    if (!this.canTrackVelocity || this.prevFrameValue === void 0 || l - this.updatedAt > d0)
      return 0;
    const r = Math.min(this.updatedAt - this.prevUpdatedAt, d0);
    return /* @__PURE__ */ xg(parseFloat(this.current) - parseFloat(this.prevFrameValue), r);
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
function nv(i, l) {
  if (i?.inherit && l) {
    const { inherit: r, ...o } = i;
    return { ...l, ...o };
  }
  return i;
}
function id(i, l) {
  const r = i?.[l] ?? i?.default ?? i;
  return r !== i ? nv(r, i) : r;
}
const Qx = {
  type: "spring",
  stiffness: 500,
  damping: 25,
  restSpeed: 10
}, Kx = (i) => ({
  type: "spring",
  stiffness: 550,
  damping: i === 0 ? 2 * Math.sqrt(550) : 30,
  restSpeed: 10
}), Jx = {
  type: "keyframes",
  duration: 0.8
}, kx = {
  type: "keyframes",
  ease: [0.25, 0.1, 0.35, 1],
  duration: 0.3
}, Px = (i, { keyframes: l }) => l.length > 2 ? Jx : Wi.has(i) ? i.startsWith("scale") ? Kx(l[1]) : Qx : kx, Fx = /* @__PURE__ */ new Set([
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
function Wx(i) {
  for (const l in i)
    if (!Fx.has(l))
      return !0;
  return !1;
}
const ld = (i, l, r, o = {}, c, h) => (d) => {
  const p = id(o, i) || {}, v = p.delay || o.delay || 0;
  let { elapsed: b = 0 } = o;
  b = b - /* @__PURE__ */ Le(v);
  const g = {
    keyframes: Array.isArray(r) ? r : [null, r],
    ease: "easeOut",
    velocity: l.getVelocity(),
    ...p,
    delay: -b,
    onUpdate: (T) => {
      l.set(T), p.onUpdate && p.onUpdate(T);
    },
    onComplete: () => {
      d(), p.onComplete && p.onComplete();
    },
    name: i,
    motionValue: l,
    element: h ? void 0 : c
  };
  Wx(p) || Object.assign(g, Px(i, g)), g.duration && (g.duration = /* @__PURE__ */ Le(g.duration)), g.repeatDelay && (g.repeatDelay = /* @__PURE__ */ Le(g.repeatDelay)), g.from !== void 0 && (g.keyframes[0] = g.from);
  let y = !1;
  if ((g.type === !1 || g.duration === 0 && !g.repeatDelay) && (Rf(g), g.delay === 0 && (y = !0)), (ga.instantAnimations || ga.skipAnimations || c?.shouldSkipAnimations || p.skipAnimations) && (y = !0, Rf(g), g.delay = 0), g.allowFlatten = !p.type && !p.ease, y && !h && l.get() !== void 0) {
    const T = ro(g.keyframes, p);
    if (T !== void 0) {
      Vt.update(() => {
        g.onUpdate(T), g.onComplete();
      });
      return;
    }
  }
  return p.isSync ? new to(g) : new Gx(g);
}, Ix = (
  // eslint-disable-next-line redos-detector/no-unsafe-regex -- false positive, as it can match a lot of words
  /^var\(--(?:([\w-]+)|([\w-]+), ?([a-zA-Z\d ()%#.,-]+))\)/u
);
function $x(i) {
  const l = Ix.exec(i);
  if (!l)
    return [,];
  const [, r, o, c] = l;
  return [`--${r ?? o}`, c];
}
function av(i, l, r = 1) {
  const [o, c] = $x(i);
  if (!o)
    return;
  const h = window.getComputedStyle(l).getPropertyValue(o);
  if (h) {
    const d = h.trim();
    return vg(d) ? parseFloat(d) : d;
  }
  return Wf(c) ? av(c, l, r + 1) : c;
}
function h0(i) {
  const l = [{}, {}];
  return i?.values.forEach((r, o) => {
    l[0][o] = r.get(), l[1][o] = r.getVelocity();
  }), l;
}
function sd(i, l, r, o) {
  if (typeof l == "function") {
    const [c, h] = h0(o);
    l = l(r !== void 0 ? r : i.custom, c, h);
  }
  if (typeof l == "string" && (l = i.variants && i.variants[l]), typeof l == "function") {
    const [c, h] = h0(o);
    l = l(r !== void 0 ? r : i.custom, c, h);
  }
  return l;
}
function Wa(i, l, r) {
  const o = i.getProps();
  return sd(o, l, r !== void 0 ? r : o.custom, i);
}
const iv = /* @__PURE__ */ new Set([
  "width",
  "height",
  "top",
  "left",
  "right",
  "bottom",
  ...Fi
]), zf = (i) => Array.isArray(i);
function t2(i, l, r) {
  i.hasValue(l) ? i.getValue(l).set(r) : i.addValue(l, ki(r));
}
function e2(i) {
  return zf(i) ? i[i.length - 1] || 0 : i;
}
function n2(i, l) {
  const r = Wa(i, l);
  let { transitionEnd: o = {}, transition: c = {}, ...h } = r || {};
  h = { ...h, ...o };
  for (const d in h) {
    const p = e2(h[d]);
    t2(i, d, p);
  }
}
const he = (i) => !!(i && i.getVelocity);
function a2(i) {
  return !!(he(i) && i.add);
}
function _f(i, l) {
  const r = i.getValue("willChange");
  if (a2(r))
    return r.add(l);
  if (!r && ga.WillChange) {
    const o = new ga.WillChange("auto");
    i.addValue("willChange", o), o.add(l);
  }
}
function ud(i) {
  return i.replace(/([A-Z])/g, (l) => `-${l.toLowerCase()}`);
}
const i2 = "framerAppearId", lv = "data-" + ud(i2);
function sv(i) {
  return i.props[lv];
}
function l2({ protectedKeys: i, needsAnimating: l }, r) {
  const o = i.hasOwnProperty(r) && l[r] !== !0;
  return l[r] = !1, o;
}
function uv(i, l, { delay: r = 0, transitionOverride: o, type: c } = {}) {
  let { transition: h, transitionEnd: d, ...p } = l;
  const v = i.getDefaultTransition();
  h = h ? nv(h, v) : v;
  const b = h?.reduceMotion, g = h?.skipAnimations;
  o && (h = o);
  const y = [], T = c && i.animationState && i.animationState.getState()[c], V = h?.path;
  V && V.animateVisualElement(i, p, h, r, y);
  for (const R in p) {
    const U = i.getValue(R, i.latestValues[R] ?? null), j = p[R];
    if (j === void 0 || T && l2(T, R))
      continue;
    const H = {
      delay: r,
      ...id(h || {}, R)
    };
    g && (H.skipAnimations = !0);
    const q = U.get();
    if (q !== void 0 && !U.isAnimating() && !Array.isArray(j) && j === q && !H.velocity) {
      Vt.update(() => U.set(j));
      continue;
    }
    let X = !1;
    if (window.MotionHandoffAnimation) {
      const dt = sv(i);
      if (dt) {
        const J = window.MotionHandoffAnimation(dt, R, Vt);
        J !== null && (H.startTime = J, X = !0);
      }
    }
    _f(i, R);
    const Q = b ?? i.shouldReduceMotion;
    U.start(ld(R, U, j, Q && iv.has(R) ? { type: !1 } : H, i, X));
    const it = U.animation;
    it && y.push(it);
  }
  if (d) {
    const R = () => Vt.update(() => {
      d && n2(i, d);
    });
    y.length ? Promise.all(y).then(R) : R();
  }
  return y;
}
function Vf(i, l, r = {}) {
  const o = Wa(i, l, r.type === "exit" ? i.presenceContext?.custom : void 0);
  let { transition: c = i.getDefaultTransition() || {} } = o || {};
  r.transitionOverride && (c = r.transitionOverride);
  const h = o ? () => Promise.all(uv(i, o, r)) : () => Promise.resolve(), d = i.variantChildren && i.variantChildren.size ? (v = 0) => {
    const { delayChildren: b = 0, staggerChildren: g, staggerDirection: y } = c;
    return s2(i, l, v, b, g, y, r);
  } : () => Promise.resolve(), { when: p } = c;
  if (p) {
    const [v, b] = p === "beforeChildren" ? [h, d] : [d, h];
    return v().then(() => b());
  } else
    return Promise.all([h(), d(r.delay)]);
}
function s2(i, l, r = 0, o = 0, c = 0, h = 1, d) {
  const p = [];
  for (const v of i.variantChildren)
    v.notify("AnimationStart", l), p.push(Vf(v, l, {
      ...d,
      delay: r + (typeof o == "function" ? 0 : o) + ev(i.variantChildren, v, o, c, h)
    }).then(() => v.notify("AnimationComplete", l)));
  return Promise.all(p);
}
function u2(i, l, r = {}) {
  i.notify("AnimationStart", l);
  let o;
  if (Array.isArray(l)) {
    const c = l.map((h) => Vf(i, h, r));
    o = Promise.all(c);
  } else if (typeof l == "string")
    o = Vf(i, l, r);
  else {
    const c = typeof l == "function" ? Wa(i, l, r.custom) : l;
    o = Promise.all(uv(i, c, r));
  }
  return o.then(() => {
    i.notify("AnimationComplete", l);
  });
}
const o2 = {
  test: (i) => i === "auto",
  parse: (i) => i
}, ov = (i) => (l) => l.test(i), rv = [Pi, F, xn, Yn, VT, _T, o2], m0 = (i) => rv.find(ov(i));
function r2(i) {
  return typeof i == "number" ? i === 0 : i !== null ? i === "none" || i === "0" || Sg(i) : !0;
}
const c2 = /* @__PURE__ */ new Set(["brightness", "contrast", "saturate", "opacity"]);
function f2(i) {
  const [l, r] = i.slice(0, -1).split("(");
  if (l === "drop-shadow")
    return i;
  const [o] = r.match(If) || [];
  if (!o)
    return i;
  const c = r.replace(o, "");
  let h = c2.has(l) ? 1 : 0;
  return o !== r && (h *= 100), l + "(" + h + c + ")";
}
const d2 = /\b([a-z-]*)\(.*?\)/gu, jf = {
  ...sn,
  getAnimatableNone: (i) => {
    const l = i.match(d2);
    return l ? l.map(f2).join(" ") : i;
  }
}, Uf = {
  ...sn,
  getAnimatableNone: (i) => {
    const l = sn.parse(i);
    return sn.createTransformer(i)(l.map((o) => typeof o == "number" ? 0 : typeof o == "object" ? { ...o, alpha: 1 } : o));
  }
}, p0 = {
  ...Pi,
  transform: Math.round
}, h2 = {
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
  scale: Hu,
  scaleX: Hu,
  scaleY: Hu,
  scaleZ: Hu,
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
  originX: e0,
  originY: e0,
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
  ...h2,
  zIndex: p0,
  // SVG
  fillOpacity: es,
  strokeOpacity: es,
  numOctaves: p0
}, m2 = {
  ...eo,
  // Color props
  color: Ft,
  backgroundColor: Ft,
  outlineColor: Ft,
  fill: Ft,
  stroke: Ft,
  // Border props
  borderColor: Ft,
  borderTopColor: Ft,
  borderRightColor: Ft,
  borderBottomColor: Ft,
  borderLeftColor: Ft,
  filter: jf,
  WebkitFilter: jf,
  mask: Uf,
  WebkitMask: Uf
}, cv = (i) => m2[i], p2 = /* @__PURE__ */ new Set([jf, Uf]);
function fv(i, l) {
  let r = cv(i);
  return p2.has(r) || (r = sn), r.getAnimatableNone ? r.getAnimatableNone(l) : void 0;
}
const y2 = /* @__PURE__ */ new Set(["auto", "none", "0"]);
function g2(i, l, r) {
  let o = 0, c;
  for (; o < i.length && !c; ) {
    const h = i[o];
    typeof h == "string" && !y2.has(h) && Ji(h).values.length && (c = i[o]), o++;
  }
  if (c && r)
    for (const h of l)
      i[h] = fv(r, c);
}
class v2 extends ad {
  constructor(l, r, o, c, h) {
    super(l, r, o, c, h, !0);
  }
  readKeyframes() {
    const { unresolvedKeyframes: l, element: r, name: o } = this;
    if (!r || !r.current)
      return;
    super.readKeyframes();
    for (let g = 0; g < l.length; g++) {
      let y = l[g];
      if (typeof y == "string" && (y = y.trim(), Wf(y))) {
        const T = av(y, r.current);
        T !== void 0 && (l[g] = T), g === l.length - 1 && (this.finalKeyframe = y);
      }
    }
    if (this.resolveNoneKeyframes(), !iv.has(o) || l.length !== 2)
      return;
    const [c, h] = l, d = m0(c), p = m0(h), v = t0(c), b = t0(h);
    if (v !== b && ya[o]) {
      this.needsMeasurement = !0;
      return;
    }
    if (d !== p)
      if (r0(d) && r0(p))
        for (let g = 0; g < l.length; g++) {
          const y = l[g];
          typeof y == "string" && (l[g] = parseFloat(y));
        }
      else ya[o] && (this.needsMeasurement = !0);
  }
  resolveNoneKeyframes() {
    const { unresolvedKeyframes: l, name: r } = this, o = [];
    for (let c = 0; c < l.length; c++)
      (l[c] === null || r2(l[c])) && o.push(c);
    o.length && g2(l, o, r);
  }
  measureInitialState() {
    const { element: l, unresolvedKeyframes: r, name: o } = this;
    if (!l || !l.current)
      return;
    o === "height" && (this.suspendedScrollY = window.pageYOffset), this.measuredOrigin = ya[o](l.measureViewportBox(), window.getComputedStyle(l.current)), r[0] = this.measuredOrigin;
    const c = r[r.length - 1];
    c !== void 0 && l.getValue(o, c).jump(c, !1);
  }
  measureEndState() {
    const { element: l, name: r, unresolvedKeyframes: o } = this;
    if (!l || !l.current)
      return;
    const c = l.getValue(r);
    c && c.jump(this.measuredOrigin, !1);
    const h = o.length - 1, d = o[h];
    o[h] = ya[r](l.measureViewportBox(), window.getComputedStyle(l.current)), d !== null && this.finalKeyframe === void 0 && (this.finalKeyframe = d), this.removedTransforms?.length && this.removedTransforms.forEach(([p, v]) => {
      l.getValue(p).set(v);
    }), this.resolveNoneKeyframes();
  }
}
const od = [
  "borderTopLeftRadius",
  "borderTopRightRadius",
  "borderBottomRightRadius",
  "borderBottomLeftRadius"
];
function dv(i, l, r) {
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
function b2(i) {
  return bg(i) && "offsetHeight" in i && !("ownerSVGElement" in i);
}
const { schedule: rd } = /* @__PURE__ */ _g(queueMicrotask, !1), ln = {
  x: !1,
  y: !1
};
function hv() {
  return ln.x || ln.y;
}
function S2(i) {
  return i === "x" || i === "y" ? ln[i] ? null : (ln[i] = !0, () => {
    ln[i] = !1;
  }) : ln.x || ln.y ? null : (ln.x = ln.y = !0, () => {
    ln.x = ln.y = !1;
  });
}
function mv(i, l) {
  const r = dv(i), o = new AbortController(), c = {
    passive: !0,
    ...l,
    signal: o.signal
  };
  return [r, c, () => o.abort()];
}
function T2(i) {
  return !(i.pointerType === "touch" || hv());
}
function x2(i, l, r = {}) {
  const [o, c, h] = mv(i, r);
  return o.forEach((d) => {
    let p = !1, v = !1, b;
    const g = () => {
      d.removeEventListener("pointerleave", R);
    }, y = (j) => {
      b && (b(j), b = void 0), g();
    }, T = (j) => {
      p = !1, window.removeEventListener("pointerup", T), window.removeEventListener("pointercancel", T), v && (v = !1, y(j));
    }, V = () => {
      p = !0, window.addEventListener("pointerup", T, c), window.addEventListener("pointercancel", T, c);
    }, R = (j) => {
      if (j.pointerType !== "touch") {
        if (p) {
          v = !0;
          return;
        }
        y(j);
      }
    }, U = (j) => {
      if (!T2(j))
        return;
      v = !1;
      const H = l(d, j);
      typeof H == "function" && (b = H, d.addEventListener("pointerleave", R, c));
    };
    d.addEventListener("pointerenter", U, c), d.addEventListener("pointerdown", V, c);
  }), h;
}
const pv = (i, l) => l ? i === l ? !0 : pv(i, l.parentElement) : !1, cd = (i) => i.pointerType === "mouse" ? typeof i.button != "number" || i.button <= 0 : i.isPrimary !== !1, E2 = /* @__PURE__ */ new Set([
  "BUTTON",
  "INPUT",
  "SELECT",
  "TEXTAREA",
  "A"
]);
function A2(i) {
  return E2.has(i.tagName) || i.isContentEditable === !0;
}
const M2 = /* @__PURE__ */ new Set(["INPUT", "SELECT", "TEXTAREA"]);
function C2(i) {
  return M2.has(i.tagName) || i.isContentEditable === !0;
}
const Xu = /* @__PURE__ */ new WeakSet();
function y0(i) {
  return (l) => {
    l.key === "Enter" && i(l);
  };
}
function of(i, l) {
  i.dispatchEvent(new PointerEvent("pointer" + l, { isPrimary: !0, bubbles: !0 }));
}
const D2 = (i, l) => {
  const r = i.currentTarget;
  if (!r)
    return;
  const o = y0(() => {
    if (Xu.has(r))
      return;
    of(r, "down");
    const c = y0(() => {
      of(r, "up");
    }), h = () => of(r, "cancel");
    r.addEventListener("keyup", c, l), r.addEventListener("blur", h, l);
  });
  r.addEventListener("keydown", o, l), r.addEventListener("blur", () => r.removeEventListener("keydown", o), l);
};
function g0(i) {
  return cd(i) && !hv();
}
const v0 = /* @__PURE__ */ new WeakSet();
function O2(i, l, r = {}) {
  const [o, c, h] = mv(i, r), d = (p) => {
    const v = p.currentTarget;
    if (!g0(p) || v0.has(p))
      return;
    Xu.add(v), r.stopPropagation && v0.add(p);
    const b = l(v, p), g = { ...c, capture: !0 }, y = (R, U) => {
      window.removeEventListener("pointerup", T, g), window.removeEventListener("pointercancel", V, g), Xu.has(v) && Xu.delete(v), g0(R) && typeof b == "function" && b(R, { success: U });
    }, T = (R) => {
      y(R, v === window || v === document || r.useGlobalTarget || pv(v, R.target));
    }, V = (R) => {
      y(R, !1);
    };
    window.addEventListener("pointerup", T, g), window.addEventListener("pointercancel", V, g);
  };
  return o.forEach((p) => {
    (r.useGlobalTarget ? window : p).addEventListener("pointerdown", d, c), b2(p) && (p.addEventListener("focus", (b) => D2(b, c)), !A2(p) && !p.hasAttribute("tabindex") && (p.tabIndex = 0));
  }), h;
}
function fd(i) {
  return bg(i) && "ownerSVGElement" in i;
}
const Zu = /* @__PURE__ */ new WeakMap();
let Qu;
const yv = (i, l, r) => (o, c) => c && c[0] ? c[0][i + "Size"] : fd(o) && "getBBox" in o ? o.getBBox()[l] : o[r], N2 = /* @__PURE__ */ yv("inline", "width", "offsetWidth"), w2 = /* @__PURE__ */ yv("block", "height", "offsetHeight");
function R2({ target: i, borderBoxSize: l }) {
  Zu.get(i)?.forEach((r) => {
    r(i, {
      get width() {
        return N2(i, l);
      },
      get height() {
        return w2(i, l);
      }
    });
  });
}
function z2(i) {
  i.forEach(R2);
}
function _2() {
  typeof ResizeObserver > "u" || (Qu = new ResizeObserver(z2));
}
function V2(i, l) {
  Qu || _2();
  const r = dv(i);
  return r.forEach((o) => {
    let c = Zu.get(o);
    c || (c = /* @__PURE__ */ new Set(), Zu.set(o, c)), c.add(l), Qu?.observe(o);
  }), () => {
    r.forEach((o) => {
      const c = Zu.get(o);
      c?.delete(l), c?.size || Qu?.unobserve(o);
    });
  };
}
const Ku = /* @__PURE__ */ new Set();
let Qi;
function j2() {
  Qi = () => {
    const i = {
      get width() {
        return window.innerWidth;
      },
      get height() {
        return window.innerHeight;
      }
    };
    Ku.forEach((l) => l(i));
  }, window.addEventListener("resize", Qi);
}
function U2(i) {
  return Ku.add(i), Qi || j2(), () => {
    Ku.delete(i), !Ku.size && typeof Qi == "function" && (window.removeEventListener("resize", Qi), Qi = void 0);
  };
}
function b0(i, l) {
  return typeof i == "function" ? U2(i) : V2(i, l);
}
function B2(i) {
  return fd(i) && i.tagName === "svg";
}
const L2 = [...rv, Ft, sn], H2 = (i) => L2.find(ov(i)), S0 = () => ({
  translate: 0,
  scale: 1,
  origin: 0,
  originPoint: 0
}), Ki = () => ({
  x: S0(),
  y: S0()
}), T0 = () => ({ min: 0, max: 0 }), It = () => ({
  x: T0(),
  y: T0()
}), Y2 = /* @__PURE__ */ new WeakMap();
function co(i) {
  return i !== null && typeof i == "object" && typeof i.start == "function";
}
function ns(i) {
  return typeof i == "string" || Array.isArray(i);
}
const dd = [
  "animate",
  "whileInView",
  "whileFocus",
  "whileHover",
  "whileTap",
  "whileDrag",
  "exit"
], hd = ["initial", ...dd];
function fo(i) {
  return co(i.animate) || hd.some((l) => ns(i[l]));
}
function gv(i) {
  return !!(fo(i) || i.variants);
}
function q2(i, l, r) {
  for (const o in l) {
    const c = l[o], h = r[o];
    if (he(c))
      i.addValue(o, c);
    else if (he(h))
      i.addValue(o, ki(c, { owner: i }));
    else if (h !== c)
      if (i.hasValue(o)) {
        const d = i.getValue(o);
        d.liveStyle === !0 ? d.jump(c) : d.hasAnimated || d.set(c);
      } else {
        const d = i.getStaticValue(o);
        i.addValue(o, ki(d !== void 0 ? d : c, { owner: i }));
      }
  }
  for (const o in r)
    l[o] === void 0 && i.removeValue(o);
  return l;
}
const no = { current: null }, md = { current: !1 }, G2 = typeof window < "u";
function vv() {
  if (md.current = !0, !!G2)
    if (window.matchMedia) {
      const i = window.matchMedia("(prefers-reduced-motion)"), l = () => no.current = i.matches;
      i.addEventListener("change", l), l();
    } else
      no.current = !1;
}
const x0 = [
  "AnimationStart",
  "AnimationComplete",
  "Update",
  "BeforeLayoutMeasure",
  "LayoutMeasure",
  "LayoutAnimationStart",
  "LayoutAnimationComplete"
];
let ao = {};
function bv(i) {
  ao = i;
}
function X2() {
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
  constructor({ parent: l, props: r, presenceContext: o, reducedMotionConfig: c, skipAnimations: h, blockInitialAnimation: d, visualState: p }, v = {}) {
    this.current = null, this.children = /* @__PURE__ */ new Set(), this.isVariantNode = !1, this.isControllingVariants = !1, this.shouldReduceMotion = null, this.shouldSkipAnimations = !1, this.values = /* @__PURE__ */ new Map(), this.KeyframeResolver = ad, this.features = {}, this.valueSubscriptions = /* @__PURE__ */ new Map(), this.prevMotionValues = {}, this.hasBeenMounted = !1, this.events = {}, this.propEventSubscriptions = {}, this.notifyUpdate = () => this.notify("Update", this.latestValues), this.render = () => {
      this.current && (this.triggerBuild(), this.renderInstance(this.current, this.renderState, this.props.style, this.projection));
    }, this.renderScheduledAt = 0, this.scheduleRender = () => {
      const V = be.now();
      this.renderScheduledAt < V && (this.renderScheduledAt = V, Vt.render(this.render, !1, !0));
    };
    const { latestValues: b, renderState: g } = p;
    this.latestValues = b, this.baseTarget = { ...b }, this.initialValues = r.initial ? { ...b } : {}, this.renderState = g, this.parent = l, this.props = r, this.presenceContext = o, this.depth = l ? l.depth + 1 : 0, this.reducedMotionConfig = c, this.skipAnimationsConfig = h, this.options = v, this.blockInitialAnimation = !!d, this.isControllingVariants = fo(r), this.isVariantNode = gv(r), this.isVariantNode && (this.variantChildren = /* @__PURE__ */ new Set()), this.manuallyAnimateOnMount = !!(l && l.current);
    const { willChange: y, ...T } = this.scrapeMotionValuesFromProps(r, {}, this);
    for (const V in T) {
      const R = T[V];
      b[V] !== void 0 && he(R) && R.set(b[V]);
    }
  }
  mount(l) {
    if (this.hasBeenMounted)
      for (const r in this.initialValues)
        this.values.get(r)?.jump(this.initialValues[r]), this.latestValues[r] = this.initialValues[r];
    this.current = l, Y2.set(l, this), this.projection && !this.projection.instance && this.projection.mount(l), this.parent && this.isVariantNode && !this.isControllingVariants && (this.removeFromVariantTree = this.parent.addVariantChild(this)), this.values.forEach((r, o) => this.bindToMotionValue(o, r)), this.reducedMotionConfig === "never" ? this.shouldReduceMotion = !1 : this.reducedMotionConfig === "always" ? this.shouldReduceMotion = !0 : (md.current || vv(), this.shouldReduceMotion = no.current), this.shouldSkipAnimations = this.skipAnimationsConfig ?? !1, this.parent?.addChild(this), this.update(this.props, this.presenceContext), this.hasBeenMounted = !0;
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
    if (this.valueSubscriptions.has(l) && this.valueSubscriptions.get(l)(), r.accelerate && tv.has(l) && this.current instanceof HTMLElement) {
      const { factory: d, keyframes: p, times: v, ease: b, duration: g } = r.accelerate, y = new Ig({
        element: this.current,
        name: l,
        keyframes: p,
        times: v,
        ease: b,
        duration: /* @__PURE__ */ Le(g)
      }), T = d(y);
      this.valueSubscriptions.set(l, () => {
        T(), y.cancel();
      });
      return;
    }
    const o = Wi.has(l);
    o && this.onBindTransform && this.onBindTransform();
    const c = r.on("change", (d) => {
      this.latestValues[l] = d, this.props.onUpdate && Vt.preRender(this.notifyUpdate), o && this.projection && (this.projection.isTransformDirty = !0), this.scheduleRender();
    });
    let h;
    typeof window < "u" && window.MotionCheckAppearSync && (h = window.MotionCheckAppearSync(this, l, r)), this.valueSubscriptions.set(l, () => {
      c(), h && h();
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
        const h = this.features[l];
        h.isMounted ? h.update() : (h.mount(), h.isMounted = !0);
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
    return this.current ? this.measureInstanceViewportBox(this.current, this.props) : It();
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
    for (let o = 0; o < x0.length; o++) {
      const c = x0[o];
      this.propEventSubscriptions[c] && (this.propEventSubscriptions[c](), delete this.propEventSubscriptions[c]);
      const h = "on" + c, d = l[h];
      d && (this.propEventSubscriptions[c] = this.on(c, d));
    }
    this.prevMotionValues = q2(this, this.scrapeMotionValuesFromProps(l, this.prevProps || {}, this), this.prevMotionValues), this.handleChildMotionValue && this.handleChildMotionValue();
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
    return o != null && (typeof o == "string" && (vg(o) || Sg(o)) ? o = parseFloat(o) : !H2(o) && sn.test(r) && (o = fv(l, r)), this.setBaseTarget(l, he(o) ? o.get() : o)), he(o) ? o.get() : o;
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
      const h = sd(this.props, r, this.presenceContext?.custom);
      h && (o = h[l]);
    }
    if (r && o !== void 0)
      return o;
    const c = this.getBaseTargetFromProps(this.props, l);
    return c !== void 0 && !he(c) ? c : this.initialValues[l] !== void 0 && o === void 0 ? void 0 : this.baseTarget[l];
  }
  on(l, r) {
    return this.events[l] || (this.events[l] = new kf()), this.events[l].add(r);
  }
  notify(l, ...r) {
    this.events[l] && this.events[l].notify(...r);
  }
  scheduleRenderMicrotask() {
    rd.render(this.render);
  }
}
class Sv extends Z2 {
  constructor() {
    super(...arguments), this.KeyframeResolver = v2;
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
function Tv({ top: i, left: l, right: r, bottom: o }) {
  return {
    x: { min: l, max: r },
    y: { min: i, max: o }
  };
}
function Q2({ x: i, y: l }) {
  return { top: l.min, right: i.max, bottom: l.max, left: i.min };
}
function K2(i, l) {
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
function Lf({ scale: i, scaleX: l, scaleY: r }) {
  return !rf(i) || !rf(l) || !rf(r);
}
function Ka(i) {
  return Lf(i) || xv(i) || i.z || i.rotate || i.rotateX || i.rotateY || i.skewX || i.skewY;
}
function xv(i) {
  return E0(i.x) || E0(i.y);
}
function E0(i) {
  return i && i !== "0%";
}
function io(i, l, r) {
  const o = i - r, c = l * o;
  return r + c;
}
function A0(i, l, r, o, c) {
  return c !== void 0 && (i = io(i, c, o)), io(i, r, o) + l;
}
function Hf(i, l = 0, r = 1, o, c) {
  i.min = A0(i.min, l, r, o, c), i.max = A0(i.max, l, r, o, c);
}
function Ev(i, { x: l, y: r }) {
  Hf(i.x, l.translate, l.scale, l.originPoint), Hf(i.y, r.translate, r.scale, r.originPoint);
}
const M0 = 0.999999999999, C0 = 1.0000000000001;
function J2(i, l, r, o = !1) {
  const c = r.length;
  if (!c)
    return;
  l.x = l.y = 1;
  let h, d;
  for (let p = 0; p < c; p++) {
    h = r[p], d = h.projectionDelta;
    const { visualElement: v } = h.options;
    v && v.props.style && v.props.style.display === "contents" || (o && h.options.layoutScroll && h.scroll && h !== h.root && (Tn(i.x, -h.scroll.offset.x), Tn(i.y, -h.scroll.offset.y)), d && (l.x *= d.x.scale, l.y *= d.y.scale, Ev(i, d)), o && Ka(h.latestValues) && Ju(i, h.latestValues, h.layout?.layoutBox));
  }
  l.x < C0 && l.x > M0 && (l.x = 1), l.y < C0 && l.y > M0 && (l.y = 1);
}
function Tn(i, l) {
  i.min += l, i.max += l;
}
function D0(i, l, r, o, c = 0.5) {
  const h = _t(i.min, i.max, c);
  Hf(i, l, r, h, o);
}
function O0(i, l) {
  return typeof i == "string" ? parseFloat(i) / 100 * (l.max - l.min) : i;
}
function Ju(i, l, r) {
  const o = r ?? i;
  D0(i.x, O0(l.x, o.x), l.scaleX, l.scale, l.originX), D0(i.y, O0(l.y, o.y), l.scaleY, l.scale, l.originY);
}
function Av(i, l) {
  return Tv(K2(i.getBoundingClientRect(), l));
}
function k2(i, l, r) {
  const o = Av(i, r), { scroll: c } = l;
  return c && (Tn(o.x, c.offset.x), Tn(o.y, c.offset.y)), o;
}
const P2 = {
  x: "translateX",
  y: "translateY",
  z: "translateZ",
  transformPerspective: "perspective"
}, F2 = Fi.length;
function W2(i, l, r) {
  let o = "", c = !0;
  for (let d = 0; d < F2; d++) {
    const p = Fi[d], v = i[p];
    if (v === void 0)
      continue;
    let b = !0;
    if (typeof v == "number")
      b = v === (p.startsWith("scale") ? 1 : 0);
    else {
      const g = parseFloat(v);
      b = p.startsWith("scale") ? g === 1 : g === 0;
    }
    if (!b || r) {
      const g = Bf(v, eo[p]);
      if (!b) {
        c = !1;
        const y = P2[p] || p;
        o += `${y}(${g}) `;
      }
      r && (l[p] = g);
    }
  }
  const h = i.pathRotation;
  return h && (c = !1, o += `rotate(${Bf(h, eo.pathRotation)}) `), o = o.trim(), r ? o = r(l, c ? "" : o) : c && (o = "none"), o;
}
function pd(i, l, r) {
  const { style: o, vars: c, transformOrigin: h } = i;
  let d = !1, p = !1;
  for (const v in l) {
    const b = l[v];
    if (Wi.has(v)) {
      d = !0;
      continue;
    } else if (jg(v)) {
      c[v] = b;
      continue;
    } else {
      const g = Bf(b, eo[v]);
      v.startsWith("origin") ? (p = !0, h[v] = g) : o[v] = g;
    }
  }
  if (l.transform || (d || r ? o.transform = W2(l, i.transform, r) : o.transform && (o.transform = "none")), p) {
    const { originX: v = "50%", originY: b = "50%", originZ: g = 0 } = h;
    o.transformOrigin = `${v} ${b} ${g}`;
  }
}
function Mv(i, { style: l, vars: r }, o, c) {
  const h = i.style;
  let d;
  for (d in l)
    h[d] = l[d];
  c?.applyProjectionStyles(h, o);
  for (d in r)
    h.setProperty(d, r[d]);
}
function N0(i, l) {
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
    const r = N0(i, l.target.x), o = N0(i, l.target.y);
    return `${r}% ${o}%`;
  }
}, I2 = {
  correct: (i, { treeScale: l, projectionDelta: r }) => {
    const o = i, c = sn.parse(i);
    if (c.length > 5)
      return o;
    const h = sn.createTransformer(i), d = typeof c[0] != "number" ? 1 : 0, p = r.x.scale * l.x, v = r.y.scale * l.y;
    c[0 + d] /= p, c[1 + d] /= v;
    const b = _t(p, v, 0.5);
    return typeof c[2 + d] == "number" && (c[2 + d] /= b), typeof c[3 + d] == "number" && (c[3 + d] /= b), h(c);
  }
}, Yf = {
  borderRadius: {
    ...kl,
    applyTo: [...od]
  },
  borderTopLeftRadius: kl,
  borderTopRightRadius: kl,
  borderBottomLeftRadius: kl,
  borderBottomRightRadius: kl,
  boxShadow: I2
};
function Cv(i, { layout: l, layoutId: r }) {
  return Wi.has(i) || i.startsWith("origin") || (l || r !== void 0) && (!!Yf[i] || i === "opacity");
}
function yd(i, l, r) {
  const o = i.style, c = l?.style, h = {};
  if (!o)
    return h;
  for (const d in o)
    (he(o[d]) || c && he(c[d]) || Cv(d, i) || r?.getValue(d)?.liveStyle !== void 0) && (h[d] = o[d]);
  return h;
}
function $2(i) {
  return window.getComputedStyle(i);
}
class tE extends Sv {
  constructor() {
    super(...arguments), this.type = "html", this.renderInstance = Mv;
  }
  mount(l) {
    oo(!!l.style), super.mount(l);
  }
  readValueFromInstance(l, r) {
    if (Wi.has(r))
      return this.projection?.isProjecting ? Cf(r) : Sx(l, r);
    {
      const o = $2(l), c = (jg(r) ? o.getPropertyValue(r) : o[r]) || 0;
      return typeof c == "string" ? c.trim() : c;
    }
  }
  measureInstanceViewportBox(l, { transformPagePoint: r }) {
    return Av(l, r);
  }
  build(l, r, o) {
    pd(l, r, o.transformTemplate);
  }
  scrapeMotionValuesFromProps(l, r, o) {
    return yd(l, r, o);
  }
}
const eE = {
  offset: "stroke-dashoffset",
  array: "stroke-dasharray"
}, nE = {
  offset: "strokeDashoffset",
  array: "strokeDasharray"
};
function aE(i, l, r = 1, o = 0, c = !0) {
  i.pathLength = 1;
  const h = c ? eE : nE;
  i[h.offset] = `${-o}`, i[h.array] = `${l} ${r}`;
}
const iE = [
  "offsetDistance",
  "offsetPath",
  "offsetRotate",
  "offsetAnchor"
];
function Dv(i, {
  attrX: l,
  attrY: r,
  attrScale: o,
  pathLength: c,
  pathSpacing: h = 1,
  pathOffset: d = 0,
  // This is object creation, which we try to avoid per-frame.
  ...p
}, v, b, g) {
  if (pd(i, p, b), v) {
    i.style.viewBox && (i.attrs.viewBox = i.style.viewBox);
    return;
  }
  i.attrs = i.style, i.style = {};
  const { attrs: y, style: T } = i;
  y.transform && (T.transform = y.transform, delete y.transform), (T.transform || y.transformOrigin) && (T.transformOrigin = y.transformOrigin ?? "50% 50%", delete y.transformOrigin), T.transform && (T.transformBox = g?.transformBox ?? "fill-box", delete y.transformBox);
  for (const V of iE)
    y[V] !== void 0 && (T[V] = y[V], delete y[V]);
  l !== void 0 && (y.x = l), r !== void 0 && (y.y = r), o !== void 0 && (y.scale = o), c !== void 0 && aE(y, c, h, d, !1);
}
const Ov = /* @__PURE__ */ new Set([
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
]), Nv = (i) => typeof i == "string" && i.toLowerCase() === "svg";
function lE(i, l, r, o) {
  Mv(i, l, void 0, o);
  for (const c in l.attrs)
    i.setAttribute(Ov.has(c) ? c : ud(c), l.attrs[c]);
}
function wv(i, l, r) {
  const o = yd(i, l, r);
  for (const c in i)
    if (he(i[c]) || he(l[c])) {
      const h = Fi.indexOf(c) !== -1 ? "attr" + c.charAt(0).toUpperCase() + c.substring(1) : c;
      o[h] = i[c];
    }
  return o;
}
class sE extends Sv {
  constructor() {
    super(...arguments), this.type = "svg", this.isSVGTag = !1, this.measureInstanceViewportBox = It;
  }
  getBaseTargetFromProps(l, r) {
    return l[r];
  }
  readValueFromInstance(l, r) {
    if (Wi.has(r)) {
      const o = cv(r);
      return o && o.default || 0;
    }
    return r = Ov.has(r) ? r : ud(r), l.getAttribute(r);
  }
  scrapeMotionValuesFromProps(l, r, o) {
    return wv(l, r, o);
  }
  build(l, r, o) {
    Dv(l, r, this.isSVGTag, o.transformTemplate, o.style);
  }
  renderInstance(l, r, o, c) {
    lE(l, r, o, c);
  }
  mount(l) {
    this.isSVGTag = Nv(l.tagName), super.mount(l);
  }
}
const uE = hd.length;
function Rv(i) {
  if (!i)
    return;
  if (!i.isControllingVariants) {
    const r = i.parent ? Rv(i.parent) || {} : {};
    return i.props.initial !== void 0 && (r.initial = i.props.initial), r;
  }
  const l = {};
  for (let r = 0; r < uE; r++) {
    const o = hd[r], c = i.props[o];
    (ns(c) || c === !1) && (l[o] = c);
  }
  return l;
}
function zv(i, l) {
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
const oE = [...dd].reverse(), rE = dd.length;
function cE(i) {
  return (l) => Promise.all(l.map(({ animation: r, options: o }) => u2(i, r, o)));
}
function fE(i) {
  let l = cE(i), r = w0(), o = !0, c = !1;
  const h = (b) => (g, y) => {
    const T = Wa(i, y, b === "exit" ? i.presenceContext?.custom : void 0);
    if (T) {
      const { transition: V, transitionEnd: R, ...U } = T;
      g = { ...g, ...U, ...R };
    }
    return g;
  };
  function d(b) {
    l = b(i);
  }
  function p(b) {
    const { props: g } = i, y = Rv(i.parent) || {}, T = [], V = /* @__PURE__ */ new Set();
    let R = {}, U = 1 / 0;
    for (let H = 0; H < rE; H++) {
      const q = oE[H], X = r[q], Q = g[q] !== void 0 ? g[q] : y[q], it = ns(Q), dt = q === b ? X.isActive : null;
      dt === !1 && (U = H);
      let J = Q === y[q] && Q !== g[q] && it;
      if (J && (o || c) && i.manuallyAnimateOnMount && (J = !1), X.protectedKeys = { ...R }, // If it isn't active and hasn't *just* been set as inactive
      !X.isActive && dt === null || // If we didn't and don't have any defined prop for this animation type
      !Q && !X.prevProp || // Or if the prop doesn't define an animation
      co(Q) || typeof Q == "boolean")
        continue;
      if (q === "exit" && X.isActive && dt !== !0) {
        X.prevResolvedValues && (R = {
          ...R,
          ...X.prevResolvedValues
        });
        continue;
      }
      const Z = dE(X.prevProp, Q);
      let Mt = Z || // If we're making this variant active, we want to always make it active
      q === b && X.isActive && !J && it || // If we removed a higher-priority variant (i is in reverse order)
      H > U && it, W = !1;
      const yt = Array.isArray(Q) ? Q : [Q];
      let ot = yt.reduce(h(q), {});
      dt === !1 && (ot = {});
      const { prevResolvedValues: $t = {} } = X, Zt = {
        ...$t,
        ...ot
      }, Ct = (B) => {
        Mt = !0, V.has(B) && (W = !0, V.delete(B)), X.needsAnimating[B] = !0;
        const at = i.getValue(B);
        at && (at.liveStyle = !1);
      };
      for (const B in Zt) {
        const at = ot[B], ft = $t[B];
        if (R.hasOwnProperty(B))
          continue;
        let Qt = !1;
        zf(at) && zf(ft) ? Qt = !zv(at, ft) || Z : Qt = at !== ft, Qt ? at != null ? Ct(B) : V.add(B) : at !== void 0 && V.has(B) ? Ct(B) : X.protectedKeys[B] = !0;
      }
      X.prevProp = Q, X.prevResolvedValues = ot, X.isActive && (R = { ...R, ...ot }), (o || c) && i.blockInitialAnimation && (Mt = !1);
      const Y = J && Z;
      Mt && (!Y || W) && T.push(...yt.map((B) => {
        const at = { type: q };
        if (typeof B == "string" && (o || c) && !Y && i.manuallyAnimateOnMount && i.parent) {
          const { parent: ft } = i, Qt = Wa(ft, B);
          if (ft.enteringChildren && Qt) {
            const { delayChildren: Fe } = Qt.transition || {};
            at.delay = ev(ft.enteringChildren, i, Fe);
          }
        }
        return {
          animation: B,
          options: at
        };
      }));
    }
    if (V.size) {
      const H = {};
      if (typeof g.initial != "boolean") {
        const q = Wa(i, Array.isArray(g.initial) ? g.initial[0] : g.initial);
        q && q.transition && (H.transition = q.transition);
      }
      V.forEach((q) => {
        const X = i.getBaseTarget(q), Q = i.getValue(q);
        Q && (Q.liveStyle = !0), H[q] = X ?? null;
      }), T.push({ animation: H });
    }
    let j = !!T.length;
    return o && (g.initial === !1 || g.initial === g.animate) && !i.manuallyAnimateOnMount && (j = !1), o = !1, c = !1, j ? l(T) : Promise.resolve();
  }
  function v(b, g) {
    if (r[b].isActive === g)
      return Promise.resolve();
    i.variantChildren?.forEach((T) => T.animationState?.setActive(b, g)), r[b].isActive = g;
    const y = p(b);
    for (const T in r)
      r[T].protectedKeys = {};
    return y;
  }
  return {
    animateChanges: p,
    setActive: v,
    setAnimateFunction: d,
    getState: () => r,
    reset: () => {
      r = w0(), c = !0;
    }
  };
}
function dE(i, l) {
  return typeof l == "string" ? l !== i : Array.isArray(l) ? !zv(l, i) : !1;
}
function Qa(i = !1) {
  return {
    isActive: i,
    protectedKeys: {},
    needsAnimating: {},
    prevResolvedValues: {}
  };
}
function w0() {
  return {
    animate: Qa(!0),
    whileInView: Qa(),
    whileHover: Qa(),
    whileTap: Qa(),
    whileDrag: Qa(),
    whileFocus: Qa(),
    exit: Qa()
  };
}
function qf(i, l) {
  i.min = l.min, i.max = l.max;
}
function an(i, l) {
  qf(i.x, l.x), qf(i.y, l.y);
}
function R0(i, l) {
  i.translate = l.translate, i.scale = l.scale, i.originPoint = l.originPoint, i.origin = l.origin;
}
const _v = 1e-4, hE = 1 - _v, mE = 1 + _v, Vv = 0.01, pE = 0 - Vv, yE = 0 + Vv;
function Se(i) {
  return i.max - i.min;
}
function gE(i, l, r) {
  return Math.abs(i - l) <= r;
}
function z0(i, l, r, o = 0.5) {
  i.origin = o, i.originPoint = _t(l.min, l.max, i.origin), i.scale = Se(r) / Se(l), i.translate = _t(r.min, r.max, i.origin) - i.originPoint, (i.scale >= hE && i.scale <= mE || isNaN(i.scale)) && (i.scale = 1), (i.translate >= pE && i.translate <= yE || isNaN(i.translate)) && (i.translate = 0);
}
function Il(i, l, r, o) {
  z0(i.x, l.x, r.x, o ? o.originX : void 0), z0(i.y, l.y, r.y, o ? o.originY : void 0);
}
function _0(i, l, r, o = 0) {
  const c = o ? _t(r.min, r.max, o) : r.min;
  i.min = c + l.min, i.max = i.min + Se(l);
}
function vE(i, l, r, o) {
  _0(i.x, l.x, r.x, o?.x), _0(i.y, l.y, r.y, o?.y);
}
function V0(i, l, r, o = 0) {
  const c = o ? _t(r.min, r.max, o) : r.min;
  i.min = l.min - c, i.max = i.min + Se(l);
}
function lo(i, l, r, o) {
  V0(i.x, l.x, r.x, o?.x), V0(i.y, l.y, r.y, o?.y);
}
function j0(i, l, r, o, c) {
  return i -= l, i = io(i, 1 / r, o), c !== void 0 && (i = io(i, 1 / c, o)), i;
}
function bE(i, l = 0, r = 1, o = 0.5, c, h = i, d = i) {
  if (xn.test(l) && (l = parseFloat(l), l = _t(d.min, d.max, l / 100) - d.min), typeof l != "number")
    return;
  let p = _t(h.min, h.max, o);
  i === h && (p -= l), i.min = j0(i.min, l, r, p, c), i.max = j0(i.max, l, r, p, c);
}
function U0(i, l, [r, o, c], h, d) {
  bE(i, l[r], l[o], l[c], l.scale, h, d);
}
const SE = ["x", "scaleX", "originX"], TE = ["y", "scaleY", "originY"];
function B0(i, l, r, o) {
  U0(i.x, l, SE, r ? r.x : void 0, o ? o.x : void 0), U0(i.y, l, TE, r ? r.y : void 0, o ? o.y : void 0);
}
function L0(i) {
  return i.translate === 0 && i.scale === 1;
}
function jv(i) {
  return L0(i.x) && L0(i.y);
}
function H0(i, l) {
  return i.min === l.min && i.max === l.max;
}
function xE(i, l) {
  return H0(i.x, l.x) && H0(i.y, l.y);
}
function Y0(i, l) {
  return Math.round(i.min) === Math.round(l.min) && Math.round(i.max) === Math.round(l.max);
}
function Uv(i, l) {
  return Y0(i.x, l.x) && Y0(i.y, l.y);
}
function q0(i) {
  return Se(i.x) / Se(i.y);
}
function G0(i, l) {
  return i.translate === l.translate && i.scale === l.scale && i.originPoint === l.originPoint;
}
function Sn(i) {
  return [i("x"), i("y")];
}
function EE(i, l, r) {
  let o = "";
  const c = i.x.translate / l.x, h = i.y.translate / l.y, d = r?.z || 0;
  if ((c || h || d) && (o = `translate3d(${c}px, ${h}px, ${d}px) `), (l.x !== 1 || l.y !== 1) && (o += `scale(${1 / l.x}, ${1 / l.y}) `), r) {
    const { transformPerspective: b, rotate: g, pathRotation: y, rotateX: T, rotateY: V, skewX: R, skewY: U } = r;
    b && (o = `perspective(${b}px) ${o}`), g && (o += `rotate(${g}deg) `), y && (o += `rotate(${y}deg) `), T && (o += `rotateX(${T}deg) `), V && (o += `rotateY(${V}deg) `), R && (o += `skewX(${R}deg) `), U && (o += `skewY(${U}deg) `);
  }
  const p = i.x.scale * l.x, v = i.y.scale * l.y;
  return (p !== 1 || v !== 1) && (o += `scale(${p}, ${v})`), o || "none";
}
const AE = od.length, X0 = (i) => typeof i == "string" ? parseFloat(i) : i, Z0 = (i) => typeof i == "number" || F.test(i);
function ME(i, l, r, o, c, h) {
  c ? (i.opacity = _t(0, r.opacity ?? 1, CE(o)), i.opacityExit = _t(l.opacity ?? 1, 0, DE(o))) : h && (i.opacity = _t(l.opacity ?? 1, r.opacity ?? 1, o));
  for (let d = 0; d < AE; d++) {
    const p = od[d];
    let v = Q0(l, p), b = Q0(r, p);
    if (v === void 0 && b === void 0)
      continue;
    v || (v = 0), b || (b = 0), v === 0 || b === 0 || Z0(v) === Z0(b) ? (i[p] = Math.max(_t(X0(v), X0(b), o), 0), (xn.test(b) || xn.test(v)) && (i[p] += "%")) : i[p] = b;
  }
  (l.rotate || r.rotate) && (i.rotate = _t(l.rotate || 0, r.rotate || 0, o));
}
function Q0(i, l) {
  return i[l] !== void 0 ? i[l] : i.borderRadius;
}
const CE = /* @__PURE__ */ Bv(0, 0.5, Ng), DE = /* @__PURE__ */ Bv(0.5, 0.95, Pe);
function Bv(i, l, r) {
  return (o) => o < i ? 0 : o > l ? 1 : r(/* @__PURE__ */ ts(i, l, o));
}
function OE(i, l, r) {
  const o = he(i) ? i : ki(i);
  return o.start(ld("", o, l, r)), o.animation;
}
function as(i, l, r, o = { passive: !0 }) {
  return i.addEventListener(l, r, o), () => i.removeEventListener(l, r, o);
}
const NE = (i, l) => i.depth - l.depth;
class wE {
  constructor() {
    this.children = [], this.isDirty = !1;
  }
  add(l) {
    Jf(this.children, l), this.isDirty = !0;
  }
  remove(l) {
    Fu(this.children, l), this.isDirty = !0;
  }
  forEach(l) {
    this.isDirty && this.children.sort(NE), this.isDirty = !1, this.children.forEach(l);
  }
}
function RE(i, l) {
  const r = be.now(), o = ({ timestamp: c }) => {
    const h = c - r;
    h >= l && (va(o), i(h - l));
  };
  return Vt.setup(o, !0), () => va(o);
}
function ku(i) {
  return he(i) ? i.get() : i;
}
class zE {
  constructor() {
    this.members = [];
  }
  add(l) {
    Jf(this.members, l);
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
      const { layoutDependency: c } = o.options, { layoutDependency: h } = l.options;
      (c === void 0 || c !== h) && (l.resumeFrom = o, r && (o.preserveOpacity = !0), o.snapshot && (l.snapshot = o.snapshot, l.snapshot.latestValues = o.animationValues || o.latestValues), l.root?.isUpdating && (l.isLayoutDirty = !0)), l.options.crossfade === !1 && o.hide();
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
}, cf = ["", "X", "Y", "Z"], _E = 1e3;
let VE = 0;
function ff(i, l, r, o) {
  const { latestValues: c } = l;
  c[i] && (r[i] = c[i], l.setStaticValue(i, 0), o && (o[i] = 0));
}
function Lv(i) {
  if (i.hasCheckedOptimisedAppear = !0, i.root === i)
    return;
  const { visualElement: l } = i.options;
  if (!l)
    return;
  const r = sv(l);
  if (window.MotionHasOptimisedAnimation(r, "transform")) {
    const { layout: c, layoutId: h } = i.options;
    window.MotionCancelOptimisedAnimation(r, "transform", Vt, !(c || h));
  }
  const { parent: o } = i;
  o && !o.hasCheckedOptimisedAppear && Lv(o);
}
function Hv({ attachResizeListener: i, defaultParent: l, measureScroll: r, checkIsScrollRoot: o, resetTransform: c }) {
  return class {
    constructor(d = {}, p = l?.()) {
      this.id = VE++, this.animationId = 0, this.animationCommitId = 0, this.children = /* @__PURE__ */ new Set(), this.options = {}, this.isTreeAnimating = !1, this.isAnimationBlocked = !1, this.isLayoutDirty = !1, this.isProjectionDirty = !1, this.isSharedProjectionDirty = !1, this.isTransformDirty = !1, this.updateManuallyBlocked = !1, this.updateBlockedByResize = !1, this.isUpdating = !1, this.isSVG = !1, this.needsReset = !1, this.shouldResetTransform = !1, this.hasCheckedOptimisedAppear = !1, this.treeScale = { x: 1, y: 1 }, this.eventHandlers = /* @__PURE__ */ new Map(), this.hasTreeAnimated = !1, this.layoutVersion = 0, this.updateScheduled = !1, this.scheduleUpdate = () => this.update(), this.projectionUpdateScheduled = !1, this.checkUpdateFailed = () => {
        this.isUpdating && (this.isUpdating = !1, this.clearAllSnapshots());
      }, this.updateProjection = () => {
        this.projectionUpdateScheduled = !1, this.nodes.forEach(BE), this.nodes.forEach(XE), this.nodes.forEach(ZE), this.nodes.forEach(LE);
      }, this.resolvedRelativeTargetAt = 0, this.linkedParentVersion = 0, this.hasProjected = !1, this.isVisible = !0, this.animationProgress = 0, this.sharedNodes = /* @__PURE__ */ new Map(), this.latestValues = d, this.root = p ? p.root || p : this, this.path = p ? [...p.path, p] : [], this.parent = p, this.depth = p ? p.depth + 1 : 0;
      for (let v = 0; v < this.path.length; v++)
        this.path[v].shouldResetTransform = !0;
      this.root === this && (this.nodes = new wE());
    }
    addEventListener(d, p) {
      return this.eventHandlers.has(d) || this.eventHandlers.set(d, new kf()), this.eventHandlers.get(d).add(p);
    }
    notifyListeners(d, ...p) {
      const v = this.eventHandlers.get(d);
      v && v.notify(...p);
    }
    hasListeners(d) {
      return this.eventHandlers.has(d);
    }
    /**
     * Lifecycles
     */
    mount(d) {
      if (this.instance)
        return;
      this.isSVG = fd(d) && !B2(d), this.instance = d;
      const { layoutId: p, layout: v, visualElement: b } = this.options;
      if (b && !b.current && b.mount(d), this.root.nodes.add(this), this.parent && this.parent.children.add(this), this.root.hasTreeAnimated && (v || p) && (this.isLayoutDirty = !0), i) {
        let g, y = 0;
        const T = () => this.root.updateBlockedByResize = !1;
        Vt.read(() => {
          y = window.innerWidth;
        }), i(d, () => {
          const V = window.innerWidth;
          V !== y && (y = V, this.root.updateBlockedByResize = !0, g && g(), g = RE(T, 250), Pu.hasAnimatedSinceResize && (Pu.hasAnimatedSinceResize = !1, this.nodes.forEach(k0)));
        });
      }
      p && this.root.registerSharedNode(p, this), this.options.animate !== !1 && b && (p || v) && this.addEventListener("didUpdate", ({ delta: g, hasLayoutChanged: y, hasRelativeLayoutChanged: T, layout: V }) => {
        if (this.isTreeAnimationBlocked()) {
          this.target = void 0, this.relativeTarget = void 0;
          return;
        }
        const R = this.options.transition || b.getDefaultTransition() || PE, { onLayoutAnimationStart: U, onLayoutAnimationComplete: j } = b.getProps(), H = !this.targetLayout || !Uv(this.targetLayout, V), q = !y && T;
        if (this.options.layoutRoot || this.resumeFrom || q || y && (H || !this.currentAnimation)) {
          this.resumeFrom && (this.resumingFrom = this.resumeFrom, this.resumingFrom.resumingFrom = void 0);
          const X = {
            ...id(R, "layout"),
            onPlay: U,
            onComplete: j
          };
          (b.shouldReduceMotion || this.options.layoutRoot) && (X.delay = 0, X.type = !1), this.startAnimation(X), this.setAnimationOrigin(g, q, X.path);
        } else
          y || k0(this), this.isLead() && this.options.onExitComplete && this.options.onExitComplete();
        this.targetLayout = V;
      });
    }
    unmount() {
      this.options.layoutId && this.willUpdate(), this.root.nodes.remove(this);
      const d = this.getStack();
      d && d.remove(this), this.parent && this.parent.children.delete(this), this.instance = void 0, this.eventHandlers.clear(), va(this.updateProjection);
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
      this.isUpdateBlocked() || (this.isUpdating = !0, this.nodes && this.nodes.forEach(QE), this.animationId++);
    }
    getTransformTemplate() {
      const { visualElement: d } = this.options;
      return d && d.getProps().transformTemplate;
    }
    willUpdate(d = !0) {
      if (this.root.hasTreeAnimated = !0, this.root.isUpdateBlocked()) {
        this.options.onExitComplete && this.options.onExitComplete();
        return;
      }
      if (window.MotionCancelOptimisedAnimation && !this.hasCheckedOptimisedAppear && Lv(this), !this.root.isUpdating && this.root.startUpdate(), this.isLayoutDirty)
        return;
      this.isLayoutDirty = !0;
      for (let g = 0; g < this.path.length; g++) {
        const y = this.path[g];
        y.shouldResetTransform = !0, (typeof y.latestValues.x == "string" || typeof y.latestValues.y == "string") && (y.isLayoutDirty = !0), y.updateScroll("snapshot"), y.options.layoutRoot && y.willUpdate(!1);
      }
      const { layoutId: p, layout: v } = this.options;
      if (p === void 0 && !v)
        return;
      const b = this.getTransformTemplate();
      this.prevTransformTemplateValue = b ? b(this.latestValues, "") : void 0, this.updateSnapshot(), d && this.notifyListeners("willUpdate");
    }
    update() {
      if (this.updateScheduled = !1, this.isUpdateBlocked()) {
        const v = this.updateBlockedByResize;
        this.unblockUpdate(), this.updateBlockedByResize = !1, this.clearAllSnapshots(), v && this.nodes.forEach(YE), this.nodes.forEach(K0);
        return;
      }
      if (this.animationId <= this.animationCommitId) {
        this.nodes.forEach(J0);
        return;
      }
      this.animationCommitId = this.animationId, this.isUpdating ? (this.isUpdating = !1, this.nodes.forEach(qE), this.nodes.forEach(GE), this.nodes.forEach(jE), this.nodes.forEach(UE)) : this.nodes.forEach(J0), this.clearAllSnapshots();
      const p = be.now();
      de.delta = En(0, 1e3 / 60, p - de.timestamp), de.timestamp = p, de.isProcessing = !0, ef.update.process(de), ef.preRender.process(de), ef.render.process(de), de.isProcessing = !1;
    }
    didUpdate() {
      this.updateScheduled || (this.updateScheduled = !0, rd.read(this.scheduleUpdate));
    }
    clearAllSnapshots() {
      this.nodes.forEach(HE), this.sharedNodes.forEach(KE);
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
      const d = this.layout;
      this.layout = this.measure(!1), this.layoutVersion++, this.layoutCorrected || (this.layoutCorrected = It()), this.isLayoutDirty = !1, this.projectionDelta = void 0, this.notifyListeners("measure", this.layout.layoutBox);
      const { visualElement: p } = this.options;
      p && p.notify("LayoutMeasure", this.layout.layoutBox, d ? d.layoutBox : void 0);
    }
    updateScroll(d = "measure") {
      let p = !!(this.options.layoutScroll && this.instance);
      if (this.scroll && this.scroll.animationId === this.root.animationId && this.scroll.phase === d && (p = !1), p && this.instance) {
        const v = o(this.instance);
        this.scroll = {
          animationId: this.root.animationId,
          phase: d,
          isRoot: v,
          offset: r(this.instance),
          wasRoot: this.scroll ? this.scroll.isRoot : v
        };
      }
    }
    resetTransform() {
      if (!c)
        return;
      const d = this.isLayoutDirty || this.shouldResetTransform || this.options.alwaysMeasureLayout, p = this.projectionDelta && !jv(this.projectionDelta), v = this.getTransformTemplate(), b = v ? v(this.latestValues, "") : void 0, g = b !== this.prevTransformTemplateValue;
      d && this.instance && (p || Ka(this.latestValues) || g) && (c(this.instance, b), this.shouldResetTransform = !1, this.scheduleRender());
    }
    measure(d = !0) {
      const p = this.measurePageBox();
      let v = this.removeElementScroll(p);
      return d && (v = this.removeTransform(v)), FE(v), {
        animationId: this.root.animationId,
        measuredBox: p,
        layoutBox: v,
        latestValues: {},
        source: this.id
      };
    }
    measurePageBox() {
      const { visualElement: d } = this.options;
      if (!d)
        return It();
      const p = d.measureViewportBox();
      if (!(this.scroll?.wasRoot || this.path.some(WE))) {
        const { scroll: b } = this.root;
        b && (Tn(p.x, b.offset.x), Tn(p.y, b.offset.y));
      }
      return p;
    }
    removeElementScroll(d) {
      const p = It();
      if (an(p, d), this.scroll?.wasRoot)
        return p;
      for (let v = 0; v < this.path.length; v++) {
        const b = this.path[v], { scroll: g, options: y } = b;
        b !== this.root && g && y.layoutScroll && (g.wasRoot && an(p, d), Tn(p.x, g.offset.x), Tn(p.y, g.offset.y));
      }
      return p;
    }
    applyTransform(d, p = !1, v) {
      const b = v || It();
      an(b, d);
      for (let g = 0; g < this.path.length; g++) {
        const y = this.path[g];
        !p && y.options.layoutScroll && y.scroll && y !== y.root && (Tn(b.x, -y.scroll.offset.x), Tn(b.y, -y.scroll.offset.y)), Ka(y.latestValues) && Ju(b, y.latestValues, y.layout?.layoutBox);
      }
      return Ka(this.latestValues) && Ju(b, this.latestValues, this.layout?.layoutBox), b;
    }
    removeTransform(d) {
      const p = It();
      an(p, d);
      for (let v = 0; v < this.path.length; v++) {
        const b = this.path[v];
        if (!Ka(b.latestValues))
          continue;
        let g;
        b.instance && (Lf(b.latestValues) && b.updateSnapshot(), g = It(), an(g, b.measurePageBox())), B0(p, b.latestValues, b.snapshot?.layoutBox, g);
      }
      return Ka(this.latestValues) && B0(p, this.latestValues), p;
    }
    setTargetDelta(d) {
      this.targetDelta = d, this.root.scheduleUpdateProjection(), this.isProjectionDirty = !0;
    }
    setOptions(d) {
      this.options = {
        ...this.options,
        ...d,
        crossfade: d.crossfade !== void 0 ? d.crossfade : !0
      };
    }
    clearMeasurements() {
      this.scroll = void 0, this.layout = void 0, this.snapshot = void 0, this.prevTransformTemplateValue = void 0, this.targetDelta = void 0, this.target = void 0, this.isLayoutDirty = !1;
    }
    forceRelativeParentToResolveTarget() {
      this.relativeParent && this.relativeParent.resolvedRelativeTargetAt !== de.timestamp && this.relativeParent.resolveTargetDelta(!0);
    }
    resolveTargetDelta(d = !1) {
      const p = this.getLead();
      this.isProjectionDirty || (this.isProjectionDirty = p.isProjectionDirty), this.isTransformDirty || (this.isTransformDirty = p.isTransformDirty), this.isSharedProjectionDirty || (this.isSharedProjectionDirty = p.isSharedProjectionDirty);
      const v = !!this.resumingFrom || this !== p;
      if (!(d || v && this.isSharedProjectionDirty || this.isProjectionDirty || this.parent?.isProjectionDirty || this.attemptToResolveRelativeTarget || this.root.updateBlockedByResize))
        return;
      const { layout: g, layoutId: y } = this.options;
      if (!this.layout || !(g || y))
        return;
      this.resolvedRelativeTargetAt = de.timestamp;
      const T = this.getClosestProjectingParent();
      T && this.linkedParentVersion !== T.layoutVersion && !T.options.layoutRoot && this.removeRelativeTarget(), !this.targetDelta && !this.relativeTarget && (this.options.layoutAnchor !== !1 && T && T.layout ? this.createRelativeTarget(T, this.layout.layoutBox, T.layout.layoutBox) : this.removeRelativeTarget()), !(!this.relativeTarget && !this.targetDelta) && (this.target || (this.target = It(), this.targetWithTransforms = It()), this.relativeTarget && this.relativeTargetOrigin && this.relativeParent && this.relativeParent.target ? (this.forceRelativeParentToResolveTarget(), vE(this.target, this.relativeTarget, this.relativeParent.target, this.options.layoutAnchor || void 0)) : this.targetDelta ? (this.resumingFrom ? this.applyTransform(this.layout.layoutBox, !1, this.target) : an(this.target, this.layout.layoutBox), Ev(this.target, this.targetDelta)) : an(this.target, this.layout.layoutBox), this.attemptToResolveRelativeTarget && (this.attemptToResolveRelativeTarget = !1, this.options.layoutAnchor !== !1 && T && !!T.resumingFrom == !!this.resumingFrom && !T.options.layoutScroll && T.target && this.animationProgress !== 1 ? this.createRelativeTarget(T, this.target, T.target) : this.relativeParent = this.relativeTarget = void 0));
    }
    getClosestProjectingParent() {
      if (!(!this.parent || Lf(this.parent.latestValues) || xv(this.parent.latestValues)))
        return this.parent.isProjecting() ? this.parent : this.parent.getClosestProjectingParent();
    }
    isProjecting() {
      return !!((this.relativeTarget || this.targetDelta || this.options.layoutRoot) && this.layout);
    }
    createRelativeTarget(d, p, v) {
      this.relativeParent = d, this.linkedParentVersion = d.layoutVersion, this.forceRelativeParentToResolveTarget(), this.relativeTarget = It(), this.relativeTargetOrigin = It(), lo(this.relativeTargetOrigin, p, v, this.options.layoutAnchor || void 0), an(this.relativeTarget, this.relativeTargetOrigin);
    }
    removeRelativeTarget() {
      this.relativeParent = this.relativeTarget = void 0;
    }
    calcProjection() {
      const d = this.getLead(), p = !!this.resumingFrom || this !== d;
      let v = !0;
      if ((this.isProjectionDirty || this.parent?.isProjectionDirty) && (v = !1), p && (this.isSharedProjectionDirty || this.isTransformDirty) && (v = !1), this.resolvedRelativeTargetAt === de.timestamp && (v = !1), v)
        return;
      const { layout: b, layoutId: g } = this.options;
      if (this.isTreeAnimating = !!(this.parent && this.parent.isTreeAnimating || this.currentAnimation || this.pendingAnimation), this.isTreeAnimating || (this.targetDelta = this.relativeTarget = void 0), !this.layout || !(b || g))
        return;
      an(this.layoutCorrected, this.layout.layoutBox);
      const y = this.treeScale.x, T = this.treeScale.y;
      J2(this.layoutCorrected, this.treeScale, this.path, p), d.layout && !d.target && (this.treeScale.x !== 1 || this.treeScale.y !== 1) && (d.target = d.layout.layoutBox, d.targetWithTransforms = It());
      const { target: V } = d;
      if (!V) {
        this.prevProjectionDelta && (this.createProjectionDeltas(), this.scheduleRender());
        return;
      }
      !this.projectionDelta || !this.prevProjectionDelta ? this.createProjectionDeltas() : (R0(this.prevProjectionDelta.x, this.projectionDelta.x), R0(this.prevProjectionDelta.y, this.projectionDelta.y)), Il(this.projectionDelta, this.layoutCorrected, V, this.latestValues), (this.treeScale.x !== y || this.treeScale.y !== T || !G0(this.projectionDelta.x, this.prevProjectionDelta.x) || !G0(this.projectionDelta.y, this.prevProjectionDelta.y)) && (this.hasProjected = !0, this.scheduleRender(), this.notifyListeners("projectionUpdate", V));
    }
    hide() {
      this.isVisible = !1;
    }
    show() {
      this.isVisible = !0;
    }
    scheduleRender(d = !0) {
      if (this.options.visualElement?.scheduleRender(), d) {
        const p = this.getStack();
        p && p.scheduleRender();
      }
      this.resumingFrom && !this.resumingFrom.instance && (this.resumingFrom = void 0);
    }
    createProjectionDeltas() {
      this.prevProjectionDelta = Ki(), this.projectionDelta = Ki(), this.projectionDeltaWithTransform = Ki();
    }
    setAnimationOrigin(d, p = !1, v) {
      const b = this.snapshot, g = b ? b.latestValues : {}, y = { ...this.latestValues }, T = Ki();
      (!this.relativeParent || !this.relativeParent.options.layoutRoot) && (this.relativeTarget = this.relativeTargetOrigin = void 0), this.attemptToResolveRelativeTarget = !p;
      const V = It(), R = b ? b.source : void 0, U = this.layout ? this.layout.source : void 0, j = R !== U, H = this.getStack(), q = !H || H.members.length <= 1, X = !!(j && !q && this.options.crossfade === !0 && !this.path.some(kE));
      this.animationProgress = 0;
      let Q;
      const it = v?.interpolateProjection(d);
      this.mixTargetDelta = (dt) => {
        const J = dt / 1e3, Z = it?.(J);
        Z ? (T.x.translate = Z.x, T.x.scale = _t(d.x.scale, 1, J), T.x.origin = d.x.origin, T.x.originPoint = d.x.originPoint, T.y.translate = Z.y, T.y.scale = _t(d.y.scale, 1, J), T.y.origin = d.y.origin, T.y.originPoint = d.y.originPoint) : (P0(T.x, d.x, J), P0(T.y, d.y, J)), this.setTargetDelta(T), this.relativeTarget && this.relativeTargetOrigin && this.layout && this.relativeParent && this.relativeParent.layout && (lo(V, this.layout.layoutBox, this.relativeParent.layout.layoutBox, this.options.layoutAnchor || void 0), JE(this.relativeTarget, this.relativeTargetOrigin, V, J), Q && xE(this.relativeTarget, Q) && (this.isProjectionDirty = !1), Q || (Q = It()), an(Q, this.relativeTarget)), j && (this.animationValues = y, ME(y, g, this.latestValues, J, X, q)), Z && Z.rotate !== void 0 && (this.animationValues || (this.animationValues = y), this.animationValues.pathRotation = Z.rotate), this.root.scheduleUpdateProjection(), this.scheduleRender(), this.animationProgress = J;
      }, this.mixTargetDelta(this.options.layoutRoot ? 1e3 : 0);
    }
    startAnimation(d) {
      this.notifyListeners("animationStart"), this.currentAnimation?.stop(), this.resumingFrom?.currentAnimation?.stop(), this.pendingAnimation && (va(this.pendingAnimation), this.pendingAnimation = void 0), this.pendingAnimation = Vt.update(() => {
        Pu.hasAnimatedSinceResize = !0, this.motionValue || (this.motionValue = ki(0)), this.motionValue.jump(0, !1), this.currentAnimation = OE(this.motionValue, [0, 1e3], {
          ...d,
          velocity: 0,
          isSync: !0,
          onUpdate: (p) => {
            this.mixTargetDelta(p), d.onUpdate && d.onUpdate(p);
          },
          onComplete: () => {
            d.onComplete && d.onComplete(), this.completeAnimation();
          }
        }), this.resumingFrom && (this.resumingFrom.currentAnimation = this.currentAnimation), this.pendingAnimation = void 0;
      });
    }
    completeAnimation() {
      this.resumingFrom && (this.resumingFrom.currentAnimation = void 0, this.resumingFrom.preserveOpacity = void 0);
      const d = this.getStack();
      d && d.exitAnimationComplete(), this.resumingFrom = this.currentAnimation = this.animationValues = void 0, this.notifyListeners("animationComplete");
    }
    finishAnimation() {
      this.currentAnimation && (this.mixTargetDelta && this.mixTargetDelta(_E), this.currentAnimation.stop()), this.completeAnimation();
    }
    applyTransformsToTarget() {
      const d = this.getLead();
      let { targetWithTransforms: p, target: v, layout: b, latestValues: g } = d;
      if (!(!p || !v || !b)) {
        if (this !== d && this.layout && b && Yv(this.options.animationType, this.layout.layoutBox, b.layoutBox)) {
          v = this.target || It();
          const y = Se(this.layout.layoutBox.x);
          v.x.min = d.target.x.min, v.x.max = v.x.min + y;
          const T = Se(this.layout.layoutBox.y);
          v.y.min = d.target.y.min, v.y.max = v.y.min + T;
        }
        an(p, v), Ju(p, g), Il(this.projectionDeltaWithTransform, this.layoutCorrected, p, g);
      }
    }
    registerSharedNode(d, p) {
      this.sharedNodes.has(d) || this.sharedNodes.set(d, new zE()), this.sharedNodes.get(d).add(p);
      const b = p.options.initialPromotionConfig;
      p.promote({
        transition: b ? b.transition : void 0,
        preserveFollowOpacity: b && b.shouldPreserveFollowOpacity ? b.shouldPreserveFollowOpacity(p) : void 0
      });
    }
    isLead() {
      const d = this.getStack();
      return d ? d.lead === this : !0;
    }
    getLead() {
      const { layoutId: d } = this.options;
      return d ? this.getStack()?.lead || this : this;
    }
    getPrevLead() {
      const { layoutId: d } = this.options;
      return d ? this.getStack()?.prevLead : void 0;
    }
    getStack() {
      const { layoutId: d } = this.options;
      if (d)
        return this.root.sharedNodes.get(d);
    }
    promote({ needsReset: d, transition: p, preserveFollowOpacity: v } = {}) {
      const b = this.getStack();
      b && b.promote(this, v), d && (this.projectionDelta = void 0, this.needsReset = !0), p && this.setOptions({ transition: p });
    }
    relegate() {
      const d = this.getStack();
      return d ? d.relegate(this) : !1;
    }
    resetSkewAndRotation() {
      const { visualElement: d } = this.options;
      if (!d)
        return;
      let p = !1;
      const { latestValues: v } = d;
      if ((v.z || v.rotate || v.rotateX || v.rotateY || v.rotateZ || v.skewX || v.skewY) && (p = !0), !p)
        return;
      const b = {};
      v.z && ff("z", d, b, this.animationValues);
      for (let g = 0; g < cf.length; g++)
        ff(`rotate${cf[g]}`, d, b, this.animationValues), ff(`skew${cf[g]}`, d, b, this.animationValues);
      d.render();
      for (const g in b)
        d.setStaticValue(g, b[g]), this.animationValues && (this.animationValues[g] = b[g]);
      d.scheduleRender();
    }
    applyProjectionStyles(d, p) {
      if (!this.instance || this.isSVG)
        return;
      if (!this.isVisible) {
        d.visibility = "hidden";
        return;
      }
      const v = this.getTransformTemplate();
      if (this.needsReset) {
        this.needsReset = !1, d.visibility = "", d.opacity = "", d.pointerEvents = ku(p?.pointerEvents) || "", d.transform = v ? v(this.latestValues, "") : "none";
        return;
      }
      const b = this.getLead();
      if (!this.projectionDelta || !this.layout || !b.target) {
        this.options.layoutId && (d.opacity = this.latestValues.opacity !== void 0 ? this.latestValues.opacity : 1, d.pointerEvents = ku(p?.pointerEvents) || ""), this.hasProjected && !Ka(this.latestValues) && (d.transform = v ? v({}, "") : "none", this.hasProjected = !1);
        return;
      }
      d.visibility = "";
      const g = b.animationValues || b.latestValues;
      this.applyTransformsToTarget();
      let y = EE(this.projectionDeltaWithTransform, this.treeScale, g);
      v && (y = v(g, y)), d.transform = y;
      const { x: T, y: V } = this.projectionDelta;
      d.transformOrigin = `${T.origin * 100}% ${V.origin * 100}% 0`, b.animationValues ? d.opacity = b === this ? g.opacity ?? this.latestValues.opacity ?? 1 : this.preserveOpacity ? this.latestValues.opacity : g.opacityExit : d.opacity = b === this ? g.opacity !== void 0 ? g.opacity : "" : g.opacityExit !== void 0 ? g.opacityExit : 0;
      for (const R in Yf) {
        if (g[R] === void 0)
          continue;
        const { correct: U, applyTo: j, isCSSVariable: H } = Yf[R], q = y === "none" ? g[R] : U(g[R], b);
        if (j) {
          const X = j.length;
          for (let Q = 0; Q < X; Q++)
            d[j[Q]] = q;
        } else
          H ? this.options.visualElement.renderState.vars[R] = q : d[R] = q;
      }
      this.options.layoutId && (d.pointerEvents = b === this ? ku(p?.pointerEvents) || "" : "none");
    }
    clearSnapshot() {
      this.resumeFrom = this.snapshot = void 0;
    }
    // Only run on root
    resetTree() {
      this.root.nodes.forEach((d) => d.currentAnimation?.stop()), this.root.nodes.forEach(K0), this.root.sharedNodes.clear();
    }
  };
}
function jE(i) {
  i.updateLayout();
}
function UE(i) {
  const l = i.resumeFrom?.snapshot || i.snapshot;
  if (i.isLead() && i.layout && l && i.hasListeners("didUpdate")) {
    const { layoutBox: r, measuredBox: o } = i.layout, { animationType: c } = i.options, h = l.source !== i.layout.source;
    if (c === "size")
      Sn((g) => {
        const y = h ? l.measuredBox[g] : l.layoutBox[g], T = Se(y);
        y.min = r[g].min, y.max = y.min + T;
      });
    else if (c === "x" || c === "y") {
      const g = c === "x" ? "y" : "x";
      qf(h ? l.measuredBox[g] : l.layoutBox[g], r[g]);
    } else Yv(c, l.layoutBox, r) && Sn((g) => {
      const y = h ? l.measuredBox[g] : l.layoutBox[g], T = Se(r[g]);
      y.max = y.min + T, i.relativeTarget && !i.currentAnimation && (i.isProjectionDirty = !0, i.relativeTarget[g].max = i.relativeTarget[g].min + T);
    });
    const d = Ki();
    Il(d, r, l.layoutBox);
    const p = Ki();
    h ? Il(p, i.applyTransform(o, !0), l.measuredBox) : Il(p, r, l.layoutBox);
    const v = !jv(d);
    let b = !1;
    if (!i.resumeFrom) {
      const g = i.getClosestProjectingParent();
      if (g && !g.resumeFrom) {
        const { snapshot: y, layout: T } = g;
        if (y && T) {
          const V = i.options.layoutAnchor || void 0, R = It();
          lo(R, l.layoutBox, y.layoutBox, V);
          const U = It();
          lo(U, r, T.layoutBox, V), Uv(R, U) || (b = !0), g.options.layoutRoot && (i.relativeTarget = U, i.relativeTargetOrigin = R, i.relativeParent = g);
        }
      }
    }
    i.notifyListeners("didUpdate", {
      layout: r,
      snapshot: l,
      delta: p,
      layoutDelta: d,
      hasLayoutChanged: v,
      hasRelativeLayoutChanged: b
    });
  } else if (i.isLead()) {
    const { onExitComplete: r } = i.options;
    r && r();
  }
  i.options.transition = void 0;
}
function BE(i) {
  i.parent && (i.isProjecting() || (i.isProjectionDirty = i.parent.isProjectionDirty), i.isSharedProjectionDirty || (i.isSharedProjectionDirty = !!(i.isProjectionDirty || i.parent.isProjectionDirty || i.parent.isSharedProjectionDirty)), i.isTransformDirty || (i.isTransformDirty = i.parent.isTransformDirty));
}
function LE(i) {
  i.isProjectionDirty = i.isSharedProjectionDirty = i.isTransformDirty = !1;
}
function HE(i) {
  i.clearSnapshot();
}
function K0(i) {
  i.clearMeasurements();
}
function YE(i) {
  i.isLayoutDirty = !0, i.updateLayout();
}
function J0(i) {
  i.isLayoutDirty = !1;
}
function qE(i) {
  i.isAnimationBlocked && i.layout && !i.isLayoutDirty && (i.snapshot = i.layout, i.isLayoutDirty = !0);
}
function GE(i) {
  const { visualElement: l } = i.options;
  l && l.getProps().onBeforeLayoutMeasure && l.notify("BeforeLayoutMeasure"), i.resetTransform();
}
function k0(i) {
  i.finishAnimation(), i.targetDelta = i.relativeTarget = i.target = void 0, i.isProjectionDirty = !0;
}
function XE(i) {
  i.resolveTargetDelta();
}
function ZE(i) {
  i.calcProjection();
}
function QE(i) {
  i.resetSkewAndRotation();
}
function KE(i) {
  i.removeLeadSnapshot();
}
function P0(i, l, r) {
  i.translate = _t(l.translate, 0, r), i.scale = _t(l.scale, 1, r), i.origin = l.origin, i.originPoint = l.originPoint;
}
function F0(i, l, r, o) {
  i.min = _t(l.min, r.min, o), i.max = _t(l.max, r.max, o);
}
function JE(i, l, r, o) {
  F0(i.x, l.x, r.x, o), F0(i.y, l.y, r.y, o);
}
function kE(i) {
  return i.animationValues && i.animationValues.opacityExit !== void 0;
}
const PE = {
  duration: 0.45,
  ease: [0.4, 0, 0.1, 1]
}, W0 = (i) => typeof navigator < "u" && navigator.userAgent && navigator.userAgent.toLowerCase().includes(i), I0 = W0("applewebkit/") && !W0("chrome/") ? Math.round : Pe;
function $0(i) {
  i.min = I0(i.min), i.max = I0(i.max);
}
function FE(i) {
  $0(i.x), $0(i.y);
}
function Yv(i, l, r) {
  return i === "position" || i === "preserve-aspect" && !gE(q0(l), q0(r), 0.2);
}
function WE(i) {
  return i !== i.root && i.scroll?.wasRoot;
}
const IE = Hv({
  attachResizeListener: (i, l) => as(i, "resize", l),
  measureScroll: () => ({
    x: document.documentElement.scrollLeft || document.body?.scrollLeft || 0,
    y: document.documentElement.scrollTop || document.body?.scrollTop || 0
  }),
  checkIsScrollRoot: () => !0
}), df = {
  current: void 0
}, qv = Hv({
  measureScroll: (i) => ({
    x: i.scrollLeft,
    y: i.scrollTop
  }),
  defaultParent: () => {
    if (!df.current) {
      const i = new IE({});
      i.mount(window), i.setOptions({ layoutScroll: !0 }), df.current = i;
    }
    return df.current;
  },
  resetTransform: (i, l) => {
    i.style.transform = l !== void 0 ? l : "none";
  },
  checkIsScrollRoot: (i) => window.getComputedStyle(i).position === "fixed"
}), Gv = K.createContext({
  transformPagePoint: (i) => i,
  isStatic: !1,
  reducedMotion: "never"
});
function $E(i = !0) {
  const l = K.useContext(Kf);
  if (l === null)
    return [!0, null];
  const { isPresent: r, onExitComplete: o, register: c } = l, h = K.useId();
  K.useEffect(() => {
    if (i)
      return c(h);
  }, [i]);
  const d = K.useCallback(() => i && o && o(h), [h, o, i]);
  return !r && o ? [!1, d] : [!0];
}
const Xv = K.createContext({ strict: !1 }), tg = {
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
let eg = !1;
function tA() {
  if (eg)
    return;
  const i = {};
  for (const l in tg)
    i[l] = {
      isEnabled: (r) => tg[l].some((o) => !!r[o])
    };
  bv(i), eg = !0;
}
function Zv() {
  return tA(), X2();
}
function eA(i) {
  const l = Zv();
  for (const r in i)
    l[r] = {
      ...l[r],
      ...i[r]
    };
  bv(l);
}
const nA = /* @__PURE__ */ new Set([
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
  return i.startsWith("while") || i.startsWith("drag") && i !== "draggable" || i.startsWith("layout") || i.startsWith("onTap") || i.startsWith("onPan") || i.startsWith("onLayout") || nA.has(i);
}
let Qv = (i) => !so(i);
function aA(i) {
  typeof i == "function" && (Qv = (l) => l.startsWith("on") ? !so(l) : i(l));
}
try {
  aA(require("@emotion/is-prop-valid").default);
} catch {
}
function iA(i, l, r) {
  const o = {};
  for (const c in i)
    c === "values" && typeof i.values == "object" || he(i[c]) || (Qv(c) || r === !0 && so(c) || !l && !so(c) || // If trying to use native HTML drag events, forward drag listeners
    i.draggable && c.startsWith("onDrag")) && (o[c] = i[c]);
  return o;
}
const ho = /* @__PURE__ */ K.createContext({});
function lA(i, l) {
  if (fo(i)) {
    const { initial: r, animate: o } = i;
    return {
      initial: r === !1 || ns(r) ? r : void 0,
      animate: ns(o) ? o : void 0
    };
  }
  return i.inherit !== !1 ? l : {};
}
function sA(i) {
  const { initial: l, animate: r } = lA(i, K.useContext(ho));
  return K.useMemo(() => ({ initial: l, animate: r }), [ng(l), ng(r)]);
}
function ng(i) {
  return Array.isArray(i) ? i.join(" ") : i;
}
const gd = () => ({
  style: {},
  transform: {},
  transformOrigin: {},
  vars: {}
});
function Kv(i, l, r) {
  for (const o in l)
    !he(l[o]) && !Cv(o, r) && (i[o] = l[o]);
}
function uA({ transformTemplate: i }, l) {
  return K.useMemo(() => {
    const r = gd();
    return pd(r, l, i), Object.assign({}, r.vars, r.style);
  }, [l]);
}
function oA(i, l) {
  const r = i.style || {}, o = {};
  return Kv(o, r, i), Object.assign(o, uA(i, l)), o;
}
function rA(i, l) {
  const r = {}, o = oA(i, l);
  return i.drag && i.dragListener !== !1 && (r.draggable = !1, o.userSelect = o.WebkitUserSelect = o.WebkitTouchCallout = "none", o.touchAction = i.drag === !0 ? "none" : `pan-${i.drag === "x" ? "y" : "x"}`), i.tabIndex === void 0 && (i.onTap || i.onTapStart || i.whileTap) && (r.tabIndex = 0), r.style = o, r;
}
const Jv = () => ({
  ...gd(),
  attrs: {}
});
function cA(i, l, r, o) {
  const c = K.useMemo(() => {
    const h = Jv();
    return Dv(h, l, Nv(o), i.transformTemplate, i.style), {
      ...h.attrs,
      style: { ...h.style }
    };
  }, [l]);
  if (i.style) {
    const h = {};
    Kv(h, i.style, i), c.style = { ...h, ...c.style };
  }
  return c;
}
const fA = [
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
function vd(i) {
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
      !!(fA.indexOf(i) > -1 || /**
       * If it contains a capital letter, it's an SVG component
       */
      /[A-Z]/u.test(i))
    )
  );
}
function dA(i, l, r, { latestValues: o }, c, h = !1, d) {
  const v = (d ?? vd(i) ? cA : rA)(l, o, c, i), b = iA(l, typeof i == "string", h), g = i !== K.Fragment ? { ...b, ...v, ref: r } : {}, { children: y } = l, T = K.useMemo(() => he(y) ? y.get() : y, [y]);
  return K.createElement(i, {
    ...g,
    children: T
  });
}
function hA({ scrapeMotionValuesFromProps: i, createRenderState: l }, r, o, c) {
  return {
    latestValues: mA(r, o, c, i),
    renderState: l()
  };
}
function mA(i, l, r, o) {
  const c = {}, h = o(i, {});
  for (const T in h)
    c[T] = ku(h[T]);
  let { initial: d, animate: p } = i;
  const v = fo(i), b = gv(i);
  l && b && !v && i.inherit !== !1 && (d === void 0 && (d = l.initial), p === void 0 && (p = l.animate));
  let g = r ? r.initial === !1 : !1;
  g = g || d === !1;
  const y = g ? p : d;
  if (y && typeof y != "boolean" && !co(y)) {
    const T = Array.isArray(y) ? y : [y];
    for (let V = 0; V < T.length; V++) {
      const R = sd(i, T[V]);
      if (R) {
        const { transitionEnd: U, transition: j, ...H } = R;
        for (const q in H) {
          let X = H[q];
          if (Array.isArray(X)) {
            const Q = g ? X.length - 1 : 0;
            X = X[Q];
          }
          X !== null && (c[q] = X);
        }
        for (const q in U)
          c[q] = U[q];
      }
    }
  }
  return c;
}
const kv = (i) => (l, r) => {
  const o = K.useContext(ho), c = K.useContext(Kf), h = () => hA(i, l, o, c);
  return r ? h() : hT(h);
}, pA = /* @__PURE__ */ kv({
  scrapeMotionValuesFromProps: yd,
  createRenderState: gd
}), yA = /* @__PURE__ */ kv({
  scrapeMotionValuesFromProps: wv,
  createRenderState: Jv
}), gA = /* @__PURE__ */ Symbol.for("motionComponentSymbol");
function vA(i, l, r) {
  const o = K.useRef(r);
  K.useInsertionEffect(() => {
    o.current = r;
  });
  const c = K.useRef(null);
  return K.useCallback((h) => {
    h && i.onMount?.(h), l && (h ? l.mount(h) : l.unmount());
    const d = o.current;
    if (typeof d == "function")
      if (h) {
        const p = d(h);
        typeof p == "function" && (c.current = p);
      } else c.current ? (c.current(), c.current = null) : d(h);
    else d && (d.current = h);
  }, [l]);
}
const Pv = K.createContext({});
function Xi(i) {
  return i && typeof i == "object" && Object.prototype.hasOwnProperty.call(i, "current");
}
function bA(i, l, r, o, c, h) {
  const { visualElement: d } = K.useContext(ho), p = K.useContext(Xv), v = K.useContext(Kf), b = K.useContext(Gv), g = b.reducedMotion, y = b.skipAnimations, T = K.useRef(null), V = K.useRef(!1);
  o = o || p.renderer, !T.current && o && (T.current = o(i, {
    visualState: l,
    parent: d,
    props: r,
    presenceContext: v,
    blockInitialAnimation: v ? v.initial === !1 : !1,
    reducedMotionConfig: g,
    skipAnimations: y,
    isSVG: h
  }), V.current && T.current && (T.current.manuallyAnimateOnMount = !0));
  const R = T.current, U = K.useContext(Pv);
  R && !R.projection && c && (R.type === "html" || R.type === "svg") && SA(T.current, r, c, U);
  const j = K.useRef(!1);
  K.useInsertionEffect(() => {
    R && j.current && R.update(r, v);
  });
  const H = r[lv], q = K.useRef(!!H && typeof window < "u" && !window.MotionHandoffIsComplete?.(H) && window.MotionHasOptimisedAnimation?.(H));
  return pT(() => {
    V.current = !0, R && (j.current = !0, window.MotionIsMounted = !0, R.updateFeatures(), R.scheduleRenderMicrotask(), q.current && R.animationState && R.animationState.animateChanges());
  }), K.useEffect(() => {
    R && (!q.current && R.animationState && R.animationState.animateChanges(), q.current && (queueMicrotask(() => {
      window.MotionHandoffMarkAsComplete?.(H);
    }), q.current = !1), R.enteringChildren = void 0);
  }), R;
}
function SA(i, l, r, o) {
  const { layoutId: c, layout: h, drag: d, dragConstraints: p, layoutScroll: v, layoutRoot: b, layoutAnchor: g, layoutCrossfade: y } = l;
  i.projection = new r(i.latestValues, l["data-framer-portal-id"] ? void 0 : Fv(i.parent)), i.projection.setOptions({
    layoutId: c,
    layout: h,
    alwaysMeasureLayout: !!d || p && Xi(p),
    visualElement: i,
    /**
     * TODO: Update options in an effect. This could be tricky as it'll be too late
     * to update by the time layout animations run.
     * We also need to fix this safeToRemove by linking it up to the one returned by usePresence,
     * ensuring it gets called if there's no potential layout animations.
     *
     */
    animationType: typeof h == "string" ? h : "both",
    initialPromotionConfig: o,
    crossfade: y,
    layoutScroll: v,
    layoutRoot: b,
    layoutAnchor: g
  });
}
function Fv(i) {
  if (i)
    return i.options.allowProjection !== !1 ? i.projection : Fv(i.parent);
}
function hf(i, { forwardMotionProps: l = !1, type: r } = {}, o, c) {
  o && eA(o);
  const h = r ? r === "svg" : vd(i), d = h ? yA : pA;
  function p(b, g) {
    let y;
    const T = {
      ...K.useContext(Gv),
      ...b,
      layoutId: TA(b)
    }, { isStatic: V } = T, R = sA(b), U = d(b, V);
    if (!V && typeof window < "u") {
      xA();
      const j = EA(T);
      y = j.MeasureLayout, R.visualElement = bA(i, U, T, c, j.ProjectionNode, h);
    }
    return w.jsxs(ho.Provider, { value: R, children: [y && R.visualElement ? w.jsx(y, { visualElement: R.visualElement, ...T }) : null, dA(i, b, vA(U, R.visualElement, g), U, V, l, h)] });
  }
  p.displayName = `motion.${typeof i == "string" ? i : `create(${i.displayName ?? i.name ?? ""})`}`;
  const v = K.forwardRef(p);
  return v[gA] = i, v;
}
function TA({ layoutId: i }) {
  const l = K.useContext(gg).id;
  return l && i !== void 0 ? l + "-" + i : i;
}
function xA(i, l) {
  K.useContext(Xv).strict;
}
function EA(i) {
  const l = Zv(), { drag: r, layout: o } = l;
  if (!r && !o)
    return {};
  const c = { ...r, ...o };
  return {
    MeasureLayout: r?.isEnabled(i) || o?.isEnabled(i) ? c.MeasureLayout : void 0,
    ProjectionNode: c.ProjectionNode
  };
}
function AA(i, l) {
  if (typeof Proxy > "u")
    return hf;
  const r = /* @__PURE__ */ new Map(), o = (h, d) => hf(h, d, i, l), c = (h, d) => o(h, d);
  return new Proxy(c, {
    /**
     * Called when `motion` is referenced with a prop: `motion.div`, `motion.input` etc.
     * The prop name is passed through as `key` and we can use that to generate a `motion`
     * DOM component with that name.
     */
    get: (h, d) => d === "create" ? o : (r.has(d) || r.set(d, hf(d, void 0, i, l)), r.get(d))
  });
}
const MA = (i, l) => l.isSVG ?? vd(i) ? new sE(l) : new tE(l, {
  allowProjection: i !== K.Fragment
});
class CA extends ba {
  /**
   * We dynamically generate the AnimationState manager as it contains a reference
   * to the underlying animation library. We only want to load that if we load this,
   * so people can optionally code split it out using the `m` component.
   */
  constructor(l) {
    super(l), l.animationState || (l.animationState = fE(l));
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
let DA = 0;
class OA extends ba {
  constructor() {
    super(...arguments), this.id = DA++, this.isExitComplete = !1;
  }
  update() {
    if (!this.node.presenceContext)
      return;
    const { isPresent: l, onExitComplete: r } = this.node.presenceContext, { isPresent: o } = this.node.prevPresenceContext || {};
    if (!this.node.animationState || l === o)
      return;
    if (l && o === !1) {
      if (this.isExitComplete) {
        const { initial: h, custom: d } = this.node.getProps();
        if (typeof h == "string" || typeof h == "object" && h !== null && !Array.isArray(h)) {
          const p = Wa(this.node, h, d);
          if (p) {
            const { transition: v, transitionEnd: b, ...g } = p;
            for (const y in g)
              this.node.getValue(y)?.jump(g[y]);
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
const NA = {
  animation: {
    Feature: CA
  },
  exit: {
    Feature: OA
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
const wA = (i) => (l) => cd(l) && i(l, us(l));
function $l(i, l, r, o) {
  return as(i, l, wA(r), o);
}
const Wv = ({ current: i }) => i ? i.ownerDocument.defaultView : null, ag = (i, l) => Math.abs(i - l);
function RA(i, l) {
  const r = ag(i.x, l.x), o = ag(i.y, l.y);
  return Math.sqrt(r ** 2 + o ** 2);
}
const ig = /* @__PURE__ */ new Set(["auto", "scroll"]);
class Iv {
  constructor(l, r, { transformPagePoint: o, contextWindow: c = window, dragSnapToOrigin: h = !1, distanceThreshold: d = 3, element: p } = {}) {
    if (this.startEvent = null, this.lastMoveEvent = null, this.lastMoveEventInfo = null, this.lastRawMoveEventInfo = null, this.handlers = {}, this.contextWindow = window, this.scrollPositions = /* @__PURE__ */ new Map(), this.removeScrollListeners = null, this.onElementScroll = (R) => {
      this.handleScroll(R.target);
    }, this.onWindowScroll = () => {
      this.handleScroll(window);
    }, this.updatePoint = () => {
      if (!(this.lastMoveEvent && this.lastMoveEventInfo))
        return;
      this.lastRawMoveEventInfo && (this.lastMoveEventInfo = Yu(this.lastRawMoveEventInfo, this.transformPagePoint));
      const R = mf(this.lastMoveEventInfo, this.history), U = this.startEvent !== null, j = RA(R.offset, { x: 0, y: 0 }) >= this.distanceThreshold;
      if (!U && !j)
        return;
      const { point: H } = R, { timestamp: q } = de;
      this.history.push({ ...H, timestamp: q });
      const { onStart: X, onMove: Q } = this.handlers;
      U || (X && X(this.lastMoveEvent, R), this.startEvent = this.lastMoveEvent), Q && Q(this.lastMoveEvent, R);
    }, this.handlePointerMove = (R, U) => {
      this.lastMoveEvent = R, this.lastRawMoveEventInfo = U, this.lastMoveEventInfo = Yu(U, this.transformPagePoint), Vt.update(this.updatePoint, !0);
    }, this.handlePointerUp = (R, U) => {
      this.end();
      const { onEnd: j, onSessionEnd: H, resumeAnimation: q } = this.handlers;
      if ((this.dragSnapToOrigin || !this.startEvent) && q && q(), !(this.lastMoveEvent && this.lastMoveEventInfo))
        return;
      const X = mf(R.type === "pointercancel" ? this.lastMoveEventInfo : Yu(U, this.transformPagePoint), this.history);
      this.startEvent && j && j(R, X), H && H(R, X);
    }, !cd(l))
      return;
    this.dragSnapToOrigin = h, this.handlers = r, this.transformPagePoint = o, this.distanceThreshold = d, this.contextWindow = c || window;
    const v = us(l), b = Yu(v, this.transformPagePoint), { point: g } = b, { timestamp: y } = de;
    this.history = [{ ...g, timestamp: y }];
    const { onSessionStart: T } = r;
    T && T(l, mf(b, this.history));
    const V = { passive: !0, capture: !0 };
    this.removeListeners = is($l(this.contextWindow, "pointermove", this.handlePointerMove, V), $l(this.contextWindow, "pointerup", this.handlePointerUp, V), $l(this.contextWindow, "pointercancel", this.handlePointerUp, V)), p && this.startScrollTracking(p);
  }
  /**
   * Start tracking scroll on ancestors and window.
   */
  startScrollTracking(l) {
    let r = l.parentElement;
    for (; r; ) {
      const o = getComputedStyle(r);
      (ig.has(o.overflowX) || ig.has(o.overflowY)) && this.scrollPositions.set(r, {
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
    }, h = { x: c.x - r.x, y: c.y - r.y };
    h.x === 0 && h.y === 0 || (o ? this.lastMoveEventInfo && (this.lastMoveEventInfo.point.x += h.x, this.lastMoveEventInfo.point.y += h.y) : this.history.length > 0 && (this.history[0].x -= h.x, this.history[0].y -= h.y), this.scrollPositions.set(l, c), Vt.update(this.updatePoint, !0));
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
function lg(i, l) {
  return { x: i.x - l.x, y: i.y - l.y };
}
function mf({ point: i }, l) {
  return {
    point: i,
    delta: lg(i, $v(l)),
    offset: lg(i, zA(l)),
    velocity: _A(l, 0.1)
  };
}
function zA(i) {
  return i[0];
}
function $v(i) {
  return i[i.length - 1];
}
function _A(i, l) {
  if (i.length < 2)
    return { x: 0, y: 0 };
  let r = i.length - 1, o = null;
  const c = $v(i);
  for (; r >= 0 && (o = i[r], !(c.timestamp - o.timestamp > /* @__PURE__ */ Le(l))); )
    r--;
  if (!o)
    return { x: 0, y: 0 };
  o === i[0] && i.length > 2 && c.timestamp - o.timestamp > /* @__PURE__ */ Le(l) * 2 && (o = i[1]);
  const h = /* @__PURE__ */ ke(c.timestamp - o.timestamp);
  if (h === 0)
    return { x: 0, y: 0 };
  const d = {
    x: (c.x - o.x) / h,
    y: (c.y - o.y) / h
  };
  return d.x === 1 / 0 && (d.x = 0), d.y === 1 / 0 && (d.y = 0), d;
}
function VA(i, { min: l, max: r }, o) {
  return l !== void 0 && i < l ? i = o ? _t(l, i, o.min) : Math.max(i, l) : r !== void 0 && i > r && (i = o ? _t(r, i, o.max) : Math.min(i, r)), i;
}
function sg(i, l, r) {
  return {
    min: l !== void 0 ? i.min + l : void 0,
    max: r !== void 0 ? i.max + r - (i.max - i.min) : void 0
  };
}
function jA(i, { top: l, left: r, bottom: o, right: c }) {
  return {
    x: sg(i.x, r, c),
    y: sg(i.y, l, o)
  };
}
function ug(i, l) {
  let r = l.min - i.min, o = l.max - i.max;
  return l.max - l.min < i.max - i.min && ([r, o] = [o, r]), { min: r, max: o };
}
function UA(i, l) {
  return {
    x: ug(i.x, l.x),
    y: ug(i.y, l.y)
  };
}
function BA(i, l) {
  let r = 0.5;
  const o = Se(i), c = Se(l);
  return c > o ? r = /* @__PURE__ */ ts(l.min, l.max - o, i.min) : o > c && (r = /* @__PURE__ */ ts(i.min, i.max - c, l.min)), En(0, 1, r);
}
function LA(i, l) {
  const r = {};
  return l.min !== void 0 && (r.min = l.min - i.min), l.max !== void 0 && (r.max = l.max - i.min), r;
}
const Gf = 0.35;
function HA(i = Gf) {
  return i === !1 ? i = 0 : i === !0 && (i = Gf), {
    x: og(i, "left", "right"),
    y: og(i, "top", "bottom")
  };
}
function og(i, l, r) {
  return {
    min: rg(i, l),
    max: rg(i, r)
  };
}
function rg(i, l) {
  return typeof i == "number" ? i : i[l] || 0;
}
const YA = /* @__PURE__ */ new WeakMap();
class qA {
  constructor(l) {
    this.openDragLock = null, this.isDragging = !1, this.currentDirection = null, this.originPoint = { x: 0, y: 0 }, this.constraints = !1, this.hasMutatedConstraints = !1, this.elastic = It(), this.latestPointerEvent = null, this.latestPanInfo = null, this.visualElement = l;
  }
  start(l, { snapToCursor: r = !1, distanceThreshold: o } = {}) {
    const { presenceContext: c } = this.visualElement;
    if (c && c.isPresent === !1)
      return;
    const h = (y) => {
      r && this.snapToCursor(us(y).point), this.stopAnimation();
    }, d = (y, T) => {
      const { drag: V, dragPropagation: R, onDragStart: U } = this.getProps();
      if (V && !R && (this.openDragLock && this.openDragLock(), this.openDragLock = S2(V), !this.openDragLock))
        return;
      this.latestPointerEvent = y, this.latestPanInfo = T, this.isDragging = !0, this.currentDirection = null, this.resolveConstraints(), this.visualElement.projection && (this.visualElement.projection.isAnimationBlocked = !0, this.visualElement.projection.target = void 0), Sn((H) => {
        let q = this.getAxisMotionValue(H).get() || 0;
        if (xn.test(q)) {
          const { projection: X } = this.visualElement;
          if (X && X.layout) {
            const Q = X.layout.layoutBox[H];
            Q && (q = Se(Q) * (parseFloat(q) / 100));
          }
        }
        this.originPoint[H] = q;
      }), U && Vt.update(() => U(y, T), !1, !0), _f(this.visualElement, "transform");
      const { animationState: j } = this.visualElement;
      j && j.setActive("whileDrag", !0);
    }, p = (y, T) => {
      this.latestPointerEvent = y, this.latestPanInfo = T;
      const { dragPropagation: V, dragDirectionLock: R, onDirectionLock: U, onDrag: j } = this.getProps();
      if (!V && !this.openDragLock)
        return;
      const { offset: H } = T;
      if (R && this.currentDirection === null) {
        this.currentDirection = XA(H), this.currentDirection !== null && U && U(this.currentDirection);
        return;
      }
      this.updateAxis("x", T.point, H), this.updateAxis("y", T.point, H), this.visualElement.render(), j && Vt.update(() => j(y, T), !1, !0);
    }, v = (y, T) => {
      this.latestPointerEvent = y, this.latestPanInfo = T, this.stop(y, T), this.latestPointerEvent = null, this.latestPanInfo = null;
    }, b = () => {
      const { dragSnapToOrigin: y } = this.getProps();
      (y || this.constraints) && this.startAnimation({ x: 0, y: 0 });
    }, { dragSnapToOrigin: g } = this.getProps();
    this.panSession = new Iv(l, {
      onSessionStart: h,
      onStart: d,
      onMove: p,
      onSessionEnd: v,
      resumeAnimation: b
    }, {
      transformPagePoint: this.visualElement.getTransformPagePoint(),
      dragSnapToOrigin: g,
      distanceThreshold: o,
      contextWindow: Wv(this.visualElement),
      element: this.visualElement.current
    });
  }
  /**
   * @internal
   */
  stop(l, r) {
    const o = l || this.latestPointerEvent, c = r || this.latestPanInfo, h = this.isDragging;
    if (this.cancel(), !h || !c || !o)
      return;
    const { velocity: d } = c;
    this.startAnimation(d);
    const { onDragEnd: p } = this.getProps();
    p && Vt.postRender(() => p(o, c));
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
    const h = this.getAxisMotionValue(l);
    let d = this.originPoint[l] + o[l];
    this.constraints && this.constraints[l] && (d = VA(d, this.constraints[l], this.elastic[l])), h.set(d);
  }
  resolveConstraints() {
    const { dragConstraints: l, dragElastic: r } = this.getProps(), o = this.visualElement.projection && !this.visualElement.projection.layout ? this.visualElement.projection.measure(!1) : this.visualElement.projection?.layout, c = this.constraints;
    l && Xi(l) ? this.constraints || (this.constraints = this.resolveRefConstraints()) : l && o ? this.constraints = jA(o.layoutBox, l) : this.constraints = !1, this.elastic = HA(r), c !== this.constraints && !Xi(l) && o && this.constraints && !this.hasMutatedConstraints && Sn((h) => {
      this.constraints !== !1 && this.getAxisMotionValue(h) && (this.constraints[h] = LA(o.layoutBox[h], this.constraints[h]));
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
    const h = k2(o, c.root, this.visualElement.getTransformPagePoint());
    let d = UA(c.layout.layoutBox, h);
    if (r) {
      const p = r(Q2(d));
      this.hasMutatedConstraints = !!p, p && (d = Tv(p));
    }
    return d;
  }
  startAnimation(l) {
    const { drag: r, dragMomentum: o, dragElastic: c, dragTransition: h, dragSnapToOrigin: d, onDragTransitionEnd: p } = this.getProps(), v = this.constraints || {}, b = Sn((g) => {
      if (!qu(g, r, this.currentDirection))
        return;
      let y = v && v[g] || {};
      (d === !0 || d === g) && (y = { min: 0, max: 0 });
      const T = c ? 200 : 1e6, V = c ? 40 : 1e7, R = {
        type: "inertia",
        velocity: o ? l[g] : 0,
        bounceStiffness: T,
        bounceDamping: V,
        timeConstant: 750,
        restDelta: 1,
        restSpeed: 10,
        ...h,
        ...y
      };
      return this.startAxisValueAnimation(g, R);
    });
    return Promise.all(b).then(p);
  }
  startAxisValueAnimation(l, r) {
    const o = this.getAxisMotionValue(l);
    return _f(this.visualElement, l), o.start(ld(l, o, 0, r, this.visualElement, !1));
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
      const { projection: c } = this.visualElement, h = this.getAxisMotionValue(r);
      if (c && c.layout) {
        const { min: d, max: p } = c.layout.layoutBox[r], v = h.get() || 0;
        h.set(l[r] - _t(d, p, 0.5) + v);
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
    Sn((d) => {
      const p = this.getAxisMotionValue(d);
      if (p && this.constraints !== !1) {
        const v = p.get();
        c[d] = BA({ min: v, max: v }, this.constraints[d]);
      }
    });
    const { transformTemplate: h } = this.visualElement.getProps();
    this.visualElement.current.style.transform = h ? h({}, "") : "none", o.root && o.root.updateScroll(), o.updateLayout(), this.constraints = !1, this.resolveConstraints(), Sn((d) => {
      if (!qu(d, l, null))
        return;
      const p = this.getAxisMotionValue(d), { min: v, max: b } = this.constraints[d];
      p.set(_t(v, b, c[d]));
    }), this.visualElement.render();
  }
  addListeners() {
    if (!this.visualElement.current)
      return;
    YA.set(this.visualElement, this);
    const l = this.visualElement.current, r = $l(l, "pointerdown", (b) => {
      const { drag: g, dragListener: y = !0 } = this.getProps(), T = b.target, V = T !== l && C2(T);
      g && y && !V && this.start(b);
    });
    let o;
    const c = () => {
      const { dragConstraints: b } = this.getProps();
      Xi(b) && b.current && (this.constraints = this.resolveRefConstraints(), o || (o = GA(l, b.current, () => this.scalePositionWithinConstraints())));
    }, { projection: h } = this.visualElement, d = h.addEventListener("measure", c);
    h && !h.layout && (h.root && h.root.updateScroll(), h.updateLayout()), Vt.read(c);
    const p = as(window, "resize", () => this.scalePositionWithinConstraints()), v = h.addEventListener("didUpdate", (({ delta: b, hasLayoutChanged: g }) => {
      this.isDragging && g && (Sn((y) => {
        const T = this.getAxisMotionValue(y);
        T && (this.originPoint[y] += b[y].translate, T.set(T.get() + b[y].translate));
      }), this.visualElement.render());
    }));
    return () => {
      p(), r(), d(), v && v(), o && o();
    };
  }
  getProps() {
    const l = this.visualElement.getProps(), { drag: r = !1, dragDirectionLock: o = !1, dragPropagation: c = !1, dragConstraints: h = !1, dragElastic: d = Gf, dragMomentum: p = !0 } = l;
    return {
      ...l,
      drag: r,
      dragDirectionLock: o,
      dragPropagation: c,
      dragConstraints: h,
      dragElastic: d,
      dragMomentum: p
    };
  }
}
function cg(i) {
  let l = !0;
  return () => {
    if (l) {
      l = !1;
      return;
    }
    i();
  };
}
function GA(i, l, r) {
  const o = b0(i, cg(r)), c = b0(l, cg(r));
  return () => {
    o(), c();
  };
}
function qu(i, l, r) {
  return (l === !0 || l === i) && (r === null || r === i);
}
function XA(i, l = 10) {
  let r = null;
  return Math.abs(i.y) > l ? r = "y" : Math.abs(i.x) > l && (r = "x"), r;
}
class ZA extends ba {
  constructor(l) {
    super(l), this.removeGroupControls = Pe, this.removeListeners = Pe, this.controls = new qA(l);
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
const pf = (i) => (l, r) => {
  i && Vt.update(() => i(l, r), !1, !0);
};
class QA extends ba {
  constructor() {
    super(...arguments), this.removePointerDownListener = Pe;
  }
  onPointerDown(l) {
    this.session = new Iv(l, this.createPanHandlers(), {
      transformPagePoint: this.node.getTransformPagePoint(),
      contextWindow: Wv(this.node)
    });
  }
  createPanHandlers() {
    const { onPanSessionStart: l, onPanStart: r, onPan: o, onPanEnd: c } = this.node.getProps();
    return {
      onSessionStart: pf(l),
      onStart: pf(r),
      onMove: pf(o),
      onEnd: (h, d) => {
        delete this.session, c && Vt.postRender(() => c(h, d));
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
let yf = !1;
class KA extends K.Component {
  /**
   * This only mounts projection nodes for components that
   * need measuring, we might want to do it for all components
   * in order to incorporate transforms
   */
  componentDidMount() {
    const { visualElement: l, layoutGroup: r, switchLayoutGroup: o, layoutId: c } = this.props, { projection: h } = l;
    h && (r.group && r.group.add(h), o && o.register && c && o.register(h), yf && h.root.didUpdate(), h.addEventListener("animationComplete", () => {
      this.safeToRemove();
    }), h.setOptions({
      ...h.options,
      layoutDependency: this.props.layoutDependency,
      onExitComplete: () => this.safeToRemove()
    })), Pu.hasEverUpdated = !0;
  }
  getSnapshotBeforeUpdate(l) {
    const { layoutDependency: r, visualElement: o, drag: c, isPresent: h } = this.props, { projection: d } = o;
    return d && (d.isPresent = h, l.layoutDependency !== r && d.setOptions({
      ...d.options,
      layoutDependency: r
    }), yf = !0, c || l.layoutDependency !== r || r === void 0 || l.isPresent !== h ? d.willUpdate() : this.safeToRemove(), l.isPresent !== h && (h ? d.promote() : d.relegate() || Vt.postRender(() => {
      const p = d.getStack();
      (!p || !p.members.length) && this.safeToRemove();
    }))), null;
  }
  componentDidUpdate() {
    const { visualElement: l, layoutAnchor: r } = this.props, { projection: o } = l;
    o && (o.options.layoutAnchor = r, o.root.didUpdate(), rd.postRender(() => {
      !o.currentAnimation && o.isLead() && this.safeToRemove();
    }));
  }
  componentWillUnmount() {
    const { visualElement: l, layoutGroup: r, switchLayoutGroup: o } = this.props, { projection: c } = l;
    yf = !0, c && (c.scheduleCheckAfterUnmount(), r && r.group && r.group.remove(c), o && o.deregister && o.deregister(c));
  }
  safeToRemove() {
    const { safeToRemove: l } = this.props;
    l && l();
  }
  render() {
    return null;
  }
}
function t1(i) {
  const [l, r] = $E(), o = K.useContext(gg);
  return w.jsx(KA, { ...i, layoutGroup: o, switchLayoutGroup: K.useContext(Pv), isPresent: l, safeToRemove: r });
}
const JA = {
  pan: {
    Feature: QA
  },
  drag: {
    Feature: ZA,
    ProjectionNode: qv,
    MeasureLayout: t1
  }
};
function fg(i, l, r) {
  const { props: o } = i;
  i.animationState && o.whileHover && i.animationState.setActive("whileHover", r === "Start");
  const c = "onHover" + r, h = o[c];
  h && Vt.postRender(() => h(l, us(l)));
}
class kA extends ba {
  mount() {
    const { current: l } = this.node;
    l && (this.unmount = x2(l, (r, o) => (fg(this.node, o, "Start"), (c) => fg(this.node, c, "End"))));
  }
  unmount() {
  }
}
class PA extends ba {
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
function dg(i, l, r) {
  const { props: o } = i;
  if (i.current instanceof HTMLButtonElement && i.current.disabled)
    return;
  i.animationState && o.whileTap && i.animationState.setActive("whileTap", r === "Start");
  const c = "onTap" + (r === "End" ? "" : r), h = o[c];
  h && Vt.postRender(() => h(l, us(l)));
}
class FA extends ba {
  mount() {
    const { current: l } = this.node;
    if (!l)
      return;
    const { globalTapTarget: r, propagate: o } = this.node.props;
    this.unmount = O2(l, (c, h) => (dg(this.node, h, "Start"), (d, { success: p }) => dg(this.node, d, p ? "End" : "Cancel")), {
      useGlobalTarget: r,
      stopPropagation: o?.tap === !1
    });
  }
  unmount() {
  }
}
const Xf = /* @__PURE__ */ new WeakMap(), gf = /* @__PURE__ */ new WeakMap(), WA = (i) => {
  const l = Xf.get(i.target);
  l && l(i);
}, IA = (i) => {
  i.forEach(WA);
};
function $A({ root: i, ...l }) {
  const r = i || document;
  gf.has(r) || gf.set(r, {});
  const o = gf.get(r), c = JSON.stringify(l);
  return o[c] || (o[c] = new IntersectionObserver(IA, { root: i, ...l })), o[c];
}
function t3(i, l, r) {
  const o = $A(l);
  return Xf.set(i, r), o.observe(i), () => {
    Xf.delete(i), o.unobserve(i);
  };
}
const e3 = {
  some: 0,
  all: 1
};
class n3 extends ba {
  constructor() {
    super(...arguments), this.hasEnteredView = !1, this.isInView = !1;
  }
  startObserver() {
    this.stopObserver?.();
    const { viewport: l = {} } = this.node.getProps(), { root: r, margin: o, amount: c = "some", once: h } = l, d = {
      root: r ? r.current : void 0,
      rootMargin: o,
      threshold: typeof c == "number" ? c : e3[c]
    }, p = (v) => {
      const { isIntersecting: b } = v;
      if (this.isInView === b || (this.isInView = b, h && !b && this.hasEnteredView))
        return;
      b && (this.hasEnteredView = !0), this.node.animationState && this.node.animationState.setActive("whileInView", b);
      const { onViewportEnter: g, onViewportLeave: y } = this.node.getProps(), T = b ? g : y;
      T && T(v);
    };
    this.stopObserver = t3(this.node.current, d, p);
  }
  mount() {
    this.startObserver();
  }
  update() {
    if (typeof IntersectionObserver > "u")
      return;
    const { props: l, prevProps: r } = this.node;
    ["amount", "margin", "root"].some(a3(l, r)) && this.startObserver();
  }
  unmount() {
    this.stopObserver?.(), this.hasEnteredView = !1, this.isInView = !1;
  }
}
function a3({ viewport: i = {} }, { viewport: l = {} } = {}) {
  return (r) => i[r] !== l[r];
}
const i3 = {
  inView: {
    Feature: n3
  },
  tap: {
    Feature: FA
  },
  focus: {
    Feature: PA
  },
  hover: {
    Feature: kA
  }
}, l3 = {
  layout: {
    ProjectionNode: qv,
    MeasureLayout: t1
  }
}, s3 = {
  ...NA,
  ...i3,
  ...JA,
  ...l3
}, u3 = /* @__PURE__ */ AA(s3, MA);
function o3() {
  !md.current && vv();
  const [i] = K.useState(no.current);
  return i;
}
const Ja = u3;
const r3 = (i) => i.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase(), c3 = (i) => i.replace(
  /^([A-Z])|[\s-_]+(\w)/g,
  (l, r, o) => o ? o.toUpperCase() : r.toLowerCase()
), hg = (i) => {
  const l = c3(i);
  return l.charAt(0).toUpperCase() + l.slice(1);
}, e1 = (...i) => i.filter((l, r, o) => !!l && l.trim() !== "" && o.indexOf(l) === r).join(" ").trim(), f3 = (i) => {
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
const h3 = K.forwardRef(
  ({
    color: i = "currentColor",
    size: l = 24,
    strokeWidth: r = 2,
    absoluteStrokeWidth: o,
    className: c = "",
    children: h,
    iconNode: d,
    ...p
  }, v) => K.createElement(
    "svg",
    {
      ref: v,
      ...d3,
      width: l,
      height: l,
      stroke: i,
      strokeWidth: o ? Number(r) * 24 / Number(l) : r,
      className: e1("lucide", c),
      ...!h && !f3(p) && { "aria-hidden": "true" },
      ...p
    },
    [
      ...d.map(([b, g]) => K.createElement(b, g)),
      ...Array.isArray(h) ? h : [h]
    ]
  )
);
const Sa = (i, l) => {
  const r = K.forwardRef(
    ({ className: o, ...c }, h) => K.createElement(h3, {
      ref: h,
      iconNode: l,
      className: e1(
        `lucide-${r3(hg(i))}`,
        `lucide-${i}`,
        o
      ),
      ...c
    })
  );
  return r.displayName = hg(i), r;
};
const m3 = [
  ["path", { d: "M5 12h14", key: "1ays0h" }],
  ["path", { d: "m12 5 7 7-7 7", key: "xquz4c" }]
], p3 = Sa("arrow-right", m3);
const y3 = [
  ["path", { d: "M7 7h10v10", key: "1tivn9" }],
  ["path", { d: "M7 17 17 7", key: "1vkiza" }]
], n1 = Sa("arrow-up-right", y3);
const g3 = [
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
], v3 = Sa("calendar-days", g3);
const b3 = [
  [
    "path",
    { d: "m21 8-2 2-1.5-3.7A2 2 0 0 0 15.646 5H8.4a2 2 0 0 0-1.903 1.257L5 10 3 8", key: "1imjwt" }
  ],
  ["path", { d: "M7 14h.01", key: "1qa3f1" }],
  ["path", { d: "M17 14h.01", key: "7oqj8z" }],
  ["rect", { width: "18", height: "8", x: "3", y: "10", rx: "2", key: "a7itu8" }],
  ["path", { d: "M5 18v2", key: "ppbyun" }],
  ["path", { d: "M19 18v2", key: "gy7782" }]
], a1 = Sa("car-front", b3);
const S3 = [
  [
    "path",
    {
      d: "m16.24 7.76-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z",
      key: "9ktpf1"
    }
  ],
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }]
], T3 = Sa("compass", S3);
const x3 = [
  ["path", { d: "M3 7V5a2 2 0 0 1 2-2h2", key: "aa7l1z" }],
  ["path", { d: "M17 3h2a2 2 0 0 1 2 2v2", key: "4qcy5o" }],
  ["path", { d: "M21 17v2a2 2 0 0 1-2 2h-2", key: "6vwrx8" }],
  ["path", { d: "M7 21H5a2 2 0 0 1-2-2v-2", key: "ioqczr" }],
  ["path", { d: "M7 12h10", key: "b7w52i" }]
], i1 = Sa("scan-line", x3);
const E3 = [
  [
    "path",
    {
      d: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
      key: "oel41y"
    }
  ],
  ["path", { d: "m9 12 2 2 4-4", key: "dzmm74" }]
], A3 = Sa("shield-check", E3);
const M3 = [
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
], C3 = Sa("sparkles", M3), D3 = lT.lazy(() => import("./yard-ShowroomScene-YHvuyv9e.js").then((i) => i.aj));
function O3({ reduce: i }) {
  const l = K.useId().replace(/:/g, "");
  return /* @__PURE__ */ w.jsxs("svg", { "aria-hidden": "true", className: "pointer-events-none absolute inset-0 h-full w-full opacity-50", viewBox: "0 0 800 600", preserveAspectRatio: "xMidYMid slice", children: [
    /* @__PURE__ */ w.jsx("defs", { children: /* @__PURE__ */ w.jsx("pattern", { id: l, width: "70", height: "70", patternUnits: "userSpaceOnUse", children: /* @__PURE__ */ w.jsx("path", { d: "M70 0H0V70", stroke: "#80b5be", strokeOpacity: ".17", fill: "none", strokeWidth: ".7" }) }) }),
    /* @__PURE__ */ w.jsx("rect", { width: "800", height: "600", fill: "url(#" + l + ")" }),
    Array.from({ length: 10 }, (r, o) => /* @__PURE__ */ w.jsx(
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
  componentDidCatch() {
    this.props.onFailure?.();
  }
  render() {
    return this.state.failed ? /* @__PURE__ */ w.jsx(Zf, {}) : this.props.children;
  }
}
function Zf({ launch3D: i }) {
  return /* @__PURE__ */ w.jsxs("div", { "data-3d-fallback": "true", className: "flex h-full w-full flex-col items-center justify-center gap-5 bg-[radial-gradient(ellipse_at_center,#294b56_0%,#102631_62%,#061823_100%)] px-5", children: [
    /* @__PURE__ */ w.jsx(a1, { className: "h-24 w-24 text-[#d2b77d]/90 sm:h-32 sm:w-32", strokeWidth: 0.65, "aria-hidden": "true" }),
    /* @__PURE__ */ w.jsx("span", { className: "text-center text-[10px] font-semibold uppercase tracking-[.29em] text-slate-300", children: "Interactive showroom concept" }),
    i && /* @__PURE__ */ w.jsx(
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
const mg = [
  { id: "three-quarter", name: "Three-quarter" },
  { id: "side", name: "Side profile" },
  { id: "front", name: "Front detail" }
], vf = [
  { id: "ocean", name: "Ocean teal", body: "#1a3d46", roof: "#203c48", swatch: "bg-[#1a3d46]" },
  { id: "champagne", name: "Champagne gold", body: "#9b8057", roof: "#b19b76", swatch: "bg-[#9b8057]" },
  { id: "silver", name: "Arctic silver", body: "#7f9aa9", roof: "#9fb1ba", swatch: "bg-[#7f9aa9]" }
];
function w3({ reduce: i, modelUrl: l }) {
  const r = K.useRef(null), [o, c] = K.useState(!1), [h, d] = K.useState(!0), [p, v] = K.useState(!1), [b, g] = K.useState(!1), [y, T] = K.useState(!1), [V, R] = K.useState("three-quarter"), [U, j] = K.useState("ocean"), [H, q] = K.useState("concept"), [X, Q] = K.useState(!1), [it, dt] = K.useState(""), [J, Z] = K.useState(!1), [Mt, W] = K.useState(!1), yt = vf.find((B) => B.id === U) || vf[0], ot = H === "studio", $t = () => Q(!0), Zt = () => {
    if (!(!tt || i || !l)) {
      if (it && !J) {
        Z(!0);
        return;
      }
      Q(!1), W(!1), q("studio");
    }
  }, Ct = () => {
    W(!0), Q(!1), q("concept");
  };
  K.useEffect(() => {
    const B = window.navigator.connection?.saveData ? "Data Saver is on. This model transfers about 9 MB." : Number(window.navigator.deviceMemory) > 0 && Number(window.navigator.deviceMemory) <= 2 ? "Your device reports limited memory. This model transfers about 9 MB." : "";
    dt(B);
  }, []), K.useEffect(() => {
    const B = window.matchMedia("(max-width: 640px) and (pointer: coarse)"), at = () => g(B.matches);
    return at(), B.addEventListener?.("change", at), () => B.removeEventListener?.("change", at);
  }, []), K.useEffect(() => {
    const B = r.current;
    if (!B) return;
    const at = () => d(document.visibilityState === "visible");
    if (at(), document.addEventListener("visibilitychange", at), !("IntersectionObserver" in window)) c(!0);
    else {
      const ft = new IntersectionObserver(([Qt]) => {
        c(Qt.isIntersecting);
      }, { rootMargin: "100px 0px", threshold: 0.01 });
      return ft.observe(B), () => {
        ft.disconnect(), document.removeEventListener("visibilitychange", at);
      };
    }
    return () => document.removeEventListener("visibilitychange", at);
  }, []), K.useEffect(() => {
    if (!(!o || !h || i || b && !y))
      try {
        const B = document.createElement("canvas"), at = B.getContext("webgl2") || B.getContext("webgl");
        v(!!at), at && at.getExtension("WEBGL_lose_context")?.loseContext();
      } catch {
        v(!1);
      }
  }, [o, h, i, b, y]);
  const Y = b && !y, tt = p && o && h && !i && !Y;
  return /* @__PURE__ */ w.jsxs(
    "div",
    {
      ref: r,
      "data-showroom-active": tt ? "true" : "false",
      "data-studio-model-ready": ot && X ? "true" : "false",
      "data-selected-model": H,
      className: "w-full",
      children: [
        /* @__PURE__ */ w.jsxs("div", { className: "relative isolate h-[300px] w-full overflow-hidden rounded-t-2xl border border-white/10 bg-[#102630] shadow-[0_28px_90px_rgba(0,0,0,.45)] sm:h-[400px] lg:h-[510px]", children: [
          tt ? /* @__PURE__ */ w.jsx(N3, { onFailure: ot ? Ct : void 0, children: /* @__PURE__ */ w.jsx(K.Suspense, { fallback: /* @__PURE__ */ w.jsx(Zf, {}), children: /* @__PURE__ */ w.jsx(
            D3,
            {
              motionAllowed: tt,
              view: V,
              paint: yt,
              modelMode: H,
              modelUrl: l,
              onStudioReady: $t
            }
          ) }) }, H) : /* @__PURE__ */ w.jsx(Zf, { launch3D: Y && !i ? () => T(!0) : void 0 }),
          /* @__PURE__ */ w.jsxs("div", { className: "pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 p-4 sm:p-7", children: [
            /* @__PURE__ */ w.jsx("span", { className: "rounded-full border border-white/25 bg-[#102630]/80 px-3 py-2 text-[9px] font-bold uppercase tracking-[.23em] text-[#e2cc9a] backdrop-blur-md", children: ot ? "PBR Model Studio" : "3D Concept Studio" }),
            /* @__PURE__ */ w.jsx("span", { className: "rounded-full border border-white/15 bg-black/25 px-3 py-2 text-[9px] font-semibold tracking-[.12em] text-slate-300 backdrop-blur-md", children: tt ? "LIVE / EXPLORE" : "VISUAL / PREVIEW" })
          ] }),
          /* @__PURE__ */ w.jsxs("div", { className: "pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-[#07141d] via-[#07141d]/75 to-transparent px-4 pb-4 pt-10 sm:px-7 sm:pb-6", children: [
            /* @__PURE__ */ w.jsxs("span", { className: "flex items-center gap-2 text-[10px] font-semibold tracking-[.13em] text-slate-200", children: [
              /* @__PURE__ */ w.jsx(i1, { className: "h-4 w-4 text-[#d6b579]" }),
              " ",
              ot ? "Licensed third-party PBR vehicle" : "Original procedural concept"
            ] }),
            /* @__PURE__ */ w.jsx("span", { className: "text-[9px] font-bold uppercase tracking-[.16em] text-[#b6c5ca]", children: ot ? X ? "DETAIL / READY" : "DETAIL / LOADING" : "CONCEPT / READY" })
          ] })
        ] }),
        /* @__PURE__ */ w.jsxs("div", { className: "flex flex-wrap items-center justify-between gap-2 border-x border-white/15 bg-[#0c202a] px-4 py-3 sm:px-6", role: "group", "aria-label": "Vehicle model detail", children: [
          /* @__PURE__ */ w.jsxs("div", { className: "flex flex-wrap gap-2", children: [
            /* @__PURE__ */ w.jsx(
              "button",
              {
                type: "button",
                "data-model-mode": "concept",
                "aria-pressed": !ot,
                onClick: () => q("concept"),
                className: "min-h-10 rounded-md border px-4 py-2 text-[10px] font-bold tracking-wide focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white " + (ot ? "border-white/25 text-slate-200 hover:border-white/60" : "border-[#d6b579] bg-[#d6b579] text-[#0b1e28]"),
                children: "Original concept"
              }
            ),
            /* @__PURE__ */ w.jsx(
              "button",
              {
                type: "button",
                "data-model-mode": "studio",
                "aria-pressed": ot,
                onClick: Zt,
                disabled: !l || i || !tt,
                className: "min-h-10 rounded-md border px-4 py-2 text-[10px] font-bold tracking-wide focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:opacity-50 " + (ot ? "border-[#d6b579] bg-[#d6b579] text-[#0b1e28]" : "border-white/25 text-slate-200 hover:border-white/60"),
                children: J && !ot ? "Confirm Studio PBR · 9 MB" : "Load Studio PBR · 9 MB"
              }
            )
          ] }),
          /* @__PURE__ */ w.jsx("span", { className: "text-[9px] font-semibold text-slate-300", children: "High-detail model loads only on request" }),
          it && !ot && /* @__PURE__ */ w.jsxs("p", { "data-device-caution": "true", className: "w-full text-xs leading-5 text-[#f2d8a9]", children: [
            it,
            " ",
            J ? "Click Confirm Studio PBR to proceed." : "A second confirmation is required."
          ] }),
          Mt && /* @__PURE__ */ w.jsx("p", { "data-studio-recovered": "true", role: "status", className: "w-full text-xs leading-5 text-[#f2d8a9]", children: "The high-detail model could not open on this device. The original showroom has been restored." })
        ] }),
        /* @__PURE__ */ w.jsxs("div", { className: "grid gap-4 rounded-b-2xl border border-t-0 border-white/15 bg-[#0c202a] px-4 py-4 sm:grid-cols-[1fr_auto] sm:items-center sm:px-6", children: [
          /* @__PURE__ */ w.jsx("div", { role: "group", "aria-label": "Showroom camera view", className: "flex flex-wrap items-center gap-2", children: mg.map((B) => /* @__PURE__ */ w.jsx(
            "button",
            {
              type: "button",
              "data-camera-view": B.id,
              "aria-pressed": V === B.id,
              onClick: () => R(B.id),
              className: "min-h-10 rounded-md border px-3 py-2 text-[10px] font-semibold tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#dfbd82] " + (V === B.id ? "border-[#d6b579] bg-[#d6b579] text-[#0b1e28]" : "border-white/20 bg-white/5 text-slate-200 hover:border-white/50"),
              children: B.name
            },
            B.id
          )) }),
          /* @__PURE__ */ w.jsx("div", { role: "group", "aria-label": "Fictional vehicle paint finish", className: "flex items-center gap-2", children: vf.map((B) => /* @__PURE__ */ w.jsx(
            "button",
            {
              type: "button",
              "data-paint-finish": B.id,
              "aria-label": B.name,
              "aria-pressed": U === B.id,
              title: B.name,
              onClick: () => j(B.id),
              className: "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#dfbd82] " + (U === B.id ? "border-[#e8c791]" : "border-white/20 hover:border-white/60"),
              children: /* @__PURE__ */ w.jsx("span", { className: "h-6 w-6 rounded-full border border-white/30 " + B.swatch, "aria-hidden": "true" })
            },
            B.id
          )) })
        ] }),
        ot && /* @__PURE__ */ w.jsxs("p", { className: "border-x border-b border-white/15 bg-[#0c202a] px-4 py-3 text-[10px] leading-5 text-slate-300 sm:px-6", children: [
          "Model: Car Concept © 2024 Eric Chadwick / Darmstadt Graphics Group GmbH, adapted from ",
          /* @__PURE__ */ w.jsx("a", { className: "text-[#dfbd82] underline underline-offset-2", href: "https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/CarConcept", target: "_blank", rel: "noopener noreferrer", children: "Khronos glTF Sample Assets" }),
          " under ",
          /* @__PURE__ */ w.jsx("a", { className: "text-[#dfbd82] underline underline-offset-2", href: "https://creativecommons.org/licenses/by/4.0/", target: "_blank", rel: "noopener noreferrer", children: "CC BY 4.0" }),
          "; insignia and plate geometry omitted. Sample asset, not client stock or manufacturer endorsement. Trademark review still pending."
        ] }),
        /* @__PURE__ */ w.jsxs("p", { className: "sr-only", role: "status", children: [
          "Showroom view: ",
          mg.find((B) => B.id === V)?.name,
          ". ",
          ot ? "Licensed Studio PBR" : "Procedural concept",
          " paint: ",
          yt.name,
          ".",
          i ? " Motion reduced." : ""
        ] })
      ]
    }
  );
}
const pg = Object.freeze({
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
    const i = document.getElementById("empire-yard-brand-settings")?.textContent, l = i ? JSON.parse(i) : {}, r = { ...pg }, o = new URL(l.editorial_assets_base || "/wp-content/themes/empire-yard-atelier/assets/editorial/", location.href);
    r.editorialAssetsBase = o.origin === location.origin && o.pathname.endsWith("/assets/editorial/") && !o.search && !o.hash ? o.href : "/wp-content/themes/empire-yard-atelier/assets/editorial/", r.editorialMedia = {};
    for (const c of [1, 2, 3]) {
      const h = l.editorial_media_urls?.[c];
      if (typeof h == "string" && h.length < 550) {
        const d = new URL(h, location.href);
        d.origin === location.origin && d.pathname.includes("/wp-content/uploads/") && !d.search && !d.hash && !d.pathname.includes("..") && (r.editorialMedia[c] = d.href);
      }
    }
    for (const c of [
      "name",
      "strapline",
      "eyebrow",
      "headline",
      "highlight",
      "description",
      "contact_label"
    ])
      typeof l[c] == "string" && l[c].trim() && (r[c] = l[c].slice(0, 320));
    if (typeof l.contact_path == "string" && /^\/(?:[a-z0-9-]+\/){1,4}$/.test(l.contact_path) && (r.contact_path = l.contact_path), Object.prototype.hasOwnProperty.call(uo, l.accent) && (r.accent = l.accent), typeof l.showroom_model_url == "string") {
      const c = new URL(l.showroom_model_url, location.href);
      c.origin === location.origin && !c.search && !c.hash && c.pathname.endsWith("/assets/models/car-concept-editorial-webp.glb") && (r.showroomModelUrl = c.href);
    }
    return r;
  } catch {
    return {
      ...pg,
      editorialAssetsBase: "/wp-content/themes/empire-yard-atelier/assets/editorial/",
      editorialMedia: {}
    };
  }
}
function bf({ children: i, href: l, primary: r = !1, palette: o = uo.gold }) {
  return /* @__PURE__ */ w.jsxs("a", { href: l, className: (r ? o.primary : "border border-white/30 bg-white/5 text-white hover:bg-white/10") + " inline-flex min-h-12 items-center justify-center gap-3 rounded-md px-6 py-3 text-xs font-extrabold uppercase tracking-[.11em] no-underline transition-colors focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-[#eecb87]", children: [
    i,
    /* @__PURE__ */ w.jsx(n1, { "aria-hidden": "true", className: "h-4 w-4" })
  ] });
}
const z3 = [
  { num: "01", icon: T3, title: "Discovery, refined.", copy: "Fictional showroom inventory with clear filters and a responsive presentation. Real stock feeds need client authorisation." },
  { num: "02", icon: i1, title: "Details worth exploring.", copy: "Honest model specifications and image spaces without fabricated availability, reviews or pricing claims." },
  { num: "03", icon: v3, title: "A smarter workshop.", copy: "The private workbench uses database-backed slot protection. Customer booking remains disabled." }
], _3 = [
  {
    num: "01",
    name: "The art of the silhouette",
    detail: "Sculpture, proportion and deliberate light",
    filename: "studio-red.webp",
    alt: "Real editorial photograph of a red performance coupe in a dark photography studio; not a vehicle offered by this demo",
    photographer: "Moses Malik Roldan",
    source: "https://unsplash.com/photos/a-red-sports-car-parked-in-a-dark-studio-bZRqT3tvryk",
    width: 1600,
    height: 1066
  },
  {
    num: "02",
    name: "Precision in profile",
    detail: "A cleaner way to reveal form",
    filename: "studio-silver.webp",
    alt: "Real editorial photograph of a silver sports coupe in profile against a dark studio backdrop; not current dealership stock",
    photographer: "Đào Hiếu",
    source: "https://unsplash.com/photos/a-sleek-white-sports-car-against-a-dark-background-S5ogDe0Uzp0",
    width: 1600,
    height: 900
  },
  {
    num: "03",
    name: "An eye for detail",
    detail: "Materials, texture and finish",
    filename: "studio-detail.webp",
    alt: "Real editorial close-up photograph of a vintage car grille and headlight; not a car for sale",
    photographer: "Serge Kutuzov",
    source: "https://unsplash.com/photos/black-car-macro-shot-TNybYN-LqJo",
    width: 1500,
    height: 930
  }
];
function V3() {
  const i = !!o3(), [l, r] = K.useState(!1), o = i || window.matchMedia("(max-width: 640px)").matches ? !1 : { opacity: 0, y: 22 }, c = R3(), h = uo[c.accent] || uo.gold;
  return /* @__PURE__ */ w.jsxs("div", { "data-react-showroom": "true", "data-brand-accent": c.accent, className: "min-h-screen bg-[#f5f2eb] font-sans text-[#0b1e28] antialiased", children: [
    /* @__PURE__ */ w.jsx("a", { href: "#main", className: "sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-white focus:p-3 focus:text-black", children: "Skip to main content" }),
    /* @__PURE__ */ w.jsx("div", { className: h.notice + " px-4 py-2 text-center text-[9px] font-black uppercase tracking-[.2em] text-[#17303b] sm:text-[10px]", children: /* @__PURE__ */ w.jsxs("span", { className: "inline-flex items-center gap-2", children: [
      /* @__PURE__ */ w.jsx(A3, { className: "h-3.5 w-3.5", "aria-hidden": "true" }),
      " Fictional design preview — no live dealership, prices or bookings"
    ] }) }),
    /* @__PURE__ */ w.jsx("header", { className: "relative z-30 border-b border-white/10 bg-[#091923] text-white", children: /* @__PURE__ */ w.jsxs("nav", { "aria-label": "Primary navigation", className: "mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-4 px-5 py-5 md:px-10 lg:py-6", children: [
      /* @__PURE__ */ w.jsxs("a", { href: "/", className: "inline-flex items-center gap-3 no-underline", "aria-label": c.name + " concept home", children: [
        /* @__PURE__ */ w.jsx("span", { className: "flex h-10 w-10 items-center justify-center rounded-full border border-[#ddb982]/65 text-[#ddb982]", children: /* @__PURE__ */ w.jsx(a1, { className: "h-6 w-6", strokeWidth: 1.3 }) }),
        /* @__PURE__ */ w.jsxs("span", { className: "text-[15px] font-black tracking-[.18em] text-white", children: [
          c.name.toUpperCase(),
          /* @__PURE__ */ w.jsx("span", { className: "mt-0.5 block text-[8px] tracking-[.32em] " + h.logo, children: c.strapline.toUpperCase() })
        ] })
      ] }),
      /* @__PURE__ */ w.jsx("button", { "aria-label": l ? "Close navigation" : "Open navigation", "aria-expanded": l, onClick: () => r(!l), className: "rounded border border-white/30 px-3 py-2 text-[11px] uppercase tracking-widest text-white md:hidden", children: l ? "Close" : "Menu" }),
      /* @__PURE__ */ w.jsxs("div", { className: (l ? "flex" : "hidden") + " w-full flex-col gap-5 md:flex md:w-auto md:flex-row md:items-center md:gap-9", children: [
        [["The studio", "#studio"], ["The collection", "#collection"], ["Experience", "#experience"], ["Inventory", "/demo-stock/"]].map(
          ([d, p]) => /* @__PURE__ */ w.jsx("a", { href: p, className: "text-[11px] font-bold uppercase tracking-[.14em] text-[#d4e0e3] no-underline hover:text-[#dfbd82]", children: d }, d)
        ),
        /* @__PURE__ */ w.jsxs("a", { href: c.contact_path, className: "inline-flex min-h-10 items-center justify-center gap-2 rounded border border-white/30 px-4 py-2 text-[10px] font-black uppercase tracking-[.12em] text-[#e6c691] no-underline hover:bg-white/10", children: [
          c.contact_label,
          " ",
          /* @__PURE__ */ w.jsx(n1, { className: "h-4 w-4" })
        ] })
      ] })
    ] }) }),
    /* @__PURE__ */ w.jsxs("main", { id: "main", children: [
      /* @__PURE__ */ w.jsxs("section", { id: "studio", "aria-labelledby": "studio-title", className: "relative isolate overflow-hidden bg-[#091923] text-white", children: [
        /* @__PURE__ */ w.jsx(O3, { reduce: i }),
        /* @__PURE__ */ w.jsx("div", { className: "pointer-events-none absolute -left-60 top-[-150px] h-[600px] w-[600px] rounded-full bg-[#22505a]/35 blur-[135px]" }),
        /* @__PURE__ */ w.jsxs("div", { className: "relative mx-auto grid max-w-[1320px] items-center gap-12 px-5 pb-10 pt-16 md:px-10 lg:min-h-[720px] lg:grid-cols-[.91fr_1.09fr] lg:gap-7 lg:pb-20 lg:pt-20", children: [
          /* @__PURE__ */ w.jsxs("div", { className: "relative z-10 max-w-[610px]", children: [
            /* @__PURE__ */ w.jsxs(Ja.p, { initial: o, animate: { opacity: 1, y: 0 }, transition: { delay: 0.05 }, className: "mb-6 inline-flex items-center gap-3 text-[10px] font-black uppercase tracking-[.27em] " + h.eyebrow, children: [
              /* @__PURE__ */ w.jsx("span", { className: "h-px w-8 bg-current" }),
              " ",
              c.eyebrow
            ] }),
            /* @__PURE__ */ w.jsxs(Ja.h1, { id: "studio-title", initial: o, animate: { opacity: 1, y: 0 }, transition: { duration: 0.7, delay: 0.12 }, className: "max-w-[11ch] font-serif text-[clamp(3.4rem,6vw,5.6rem)] leading-[.92] tracking-[-.068em] text-[#fffdf7]", children: [
              c.headline,
              " ",
              /* @__PURE__ */ w.jsx("em", { className: "font-normal " + h.highlight, children: c.highlight })
            ] }),
            /* @__PURE__ */ w.jsx(Ja.p, { initial: o, animate: { opacity: 1, y: 0 }, transition: { delay: 0.22 }, className: "mb-8 mt-7 max-w-[50ch] text-[15px] leading-[1.85] text-[#bacbd2] sm:text-base", children: c.description }),
            /* @__PURE__ */ w.jsxs(Ja.div, { initial: o, animate: { opacity: 1, y: 0 }, transition: { delay: 0.3 }, className: "flex flex-wrap gap-3", children: [
              /* @__PURE__ */ w.jsx(bf, { primary: !0, palette: h, href: "/demo-stock/", children: "Explore fictional stock" }),
              /* @__PURE__ */ w.jsx(bf, { href: "#experience", children: "Discover the concept" })
            ] }),
            /* @__PURE__ */ w.jsxs("div", { className: "mt-10 flex flex-wrap items-center gap-5 border-t border-white/15 pt-5 text-[10px] uppercase tracking-[.14em] text-[#aabdc4]", children: [
              /* @__PURE__ */ w.jsxs("span", { className: "inline-flex items-center gap-2", children: [
                /* @__PURE__ */ w.jsx(C3, { className: "h-4 w-4 text-[#dcbc85]" }),
                " React + Three.js"
              ] }),
              /* @__PURE__ */ w.jsx("span", { children: "Mobile-first" }),
              /* @__PURE__ */ w.jsx("span", { children: "WordPress native" })
            ] })
          ] }),
          /* @__PURE__ */ w.jsxs(Ja.div, { initial: o === !1 ? !1 : { opacity: 0, x: 28 }, animate: { opacity: 1, x: 0 }, transition: { duration: 0.9, delay: 0.1 }, className: "relative z-10", children: [
            /* @__PURE__ */ w.jsx(w3, { reduce: i, modelUrl: c.showroomModelUrl }),
            /* @__PURE__ */ w.jsx("p", { className: "mt-3 text-center text-[10px] font-semibold uppercase tracking-[.15em] text-[#899da5]", children: "Illustrative 3D geometry — no real manufacturer design" })
          ] })
        ] }),
        /* @__PURE__ */ w.jsx("div", { className: "relative border-t border-white/10 bg-black/20", children: /* @__PURE__ */ w.jsxs("div", { className: "mx-auto flex max-w-[1320px] flex-wrap justify-between gap-3 px-5 py-5 text-[10px] font-semibold uppercase tracking-[.18em] text-[#b4c8ce] md:px-10", children: [
          /* @__PURE__ */ w.jsx("span", { children: "01 — A digital showroom" }),
          /* @__PURE__ */ w.jsx("span", { children: "02 — Evidence-led inventory" }),
          /* @__PURE__ */ w.jsx("span", { children: "03 — Private workshop intelligence" })
        ] }) })
      ] }),
      /* @__PURE__ */ w.jsx("section", { id: "experience", className: "bg-[#f5f2eb] px-5 py-20 md:px-10 md:py-28", children: /* @__PURE__ */ w.jsxs("div", { className: "mx-auto max-w-[1240px]", children: [
        /* @__PURE__ */ w.jsxs("div", { className: "mb-12 grid items-end gap-7 lg:grid-cols-[1.05fr_.95fr]", children: [
          /* @__PURE__ */ w.jsxs("div", { children: [
            /* @__PURE__ */ w.jsx("p", { className: "mb-3 text-[11px] font-extrabold uppercase tracking-[.22em] text-[#916d3b]", children: "Luxury in every interaction" }),
            /* @__PURE__ */ w.jsxs("h2", { className: "max-w-[15ch] font-serif text-[clamp(2.9rem,5vw,5.1rem)] leading-[1.08] tracking-[-.06em]", children: [
              "Built to make an ",
              /* @__PURE__ */ w.jsx("em", { children: "impression." })
            ] })
          ] }),
          /* @__PURE__ */ w.jsx("p", { className: "max-w-[55ch] text-base leading-[1.9] text-[#596a71]", children: "A dealership website should feel as considered as the vehicles it presents. This demo connects visual polish to practical administration without pretending a customer has gone live." })
        ] }),
        /* @__PURE__ */ w.jsx("div", { className: "grid gap-4 md:grid-cols-3", children: z3.map(({ num: d, icon: p, title: v, copy: b }) => /* @__PURE__ */ w.jsxs(Ja.article, { whileHover: i ? void 0 : { y: -5 }, className: "flex min-h-[310px] flex-col rounded-lg border border-[#dce2df] bg-white p-7 shadow-[0_22px_55px_rgba(8,25,35,.035)] sm:p-9", children: [
          /* @__PURE__ */ w.jsxs("div", { className: "mb-auto flex items-start justify-between", children: [
            /* @__PURE__ */ w.jsx("span", { className: "text-xs font-extrabold tracking-[.24em] text-[#b39462]", children: d }),
            /* @__PURE__ */ w.jsx(p, { className: "h-8 w-8 text-[#294f5b]", strokeWidth: 1.3 })
          ] }),
          /* @__PURE__ */ w.jsx("h3", { className: "mt-10 font-serif text-3xl tracking-tight", children: v }),
          /* @__PURE__ */ w.jsx("p", { className: "mt-3 text-sm leading-[1.8] text-[#64757b]", children: b })
        ] }, d)) })
      ] }) }),
      /* @__PURE__ */ w.jsx("section", { id: "collection", className: "bg-[#edece6] px-5 py-20 md:px-10 md:py-28", children: /* @__PURE__ */ w.jsxs("div", { className: "mx-auto max-w-[1240px]", children: [
        /* @__PURE__ */ w.jsxs("div", { className: "mb-10 flex flex-wrap items-end justify-between gap-6", children: [
          /* @__PURE__ */ w.jsxs("div", { children: [
            /* @__PURE__ */ w.jsx("p", { className: "mb-3 text-[11px] font-extrabold uppercase tracking-[.22em] text-[#916d3b]", children: "The collection" }),
            /* @__PURE__ */ w.jsx("h2", { className: "font-serif text-[clamp(2.9rem,5vw,5rem)] leading-[1.08] tracking-[-.06em]", children: "Explore the possibilities." })
          ] }),
          /* @__PURE__ */ w.jsxs("a", { href: "/demo-stock/", className: "inline-flex items-center gap-2 border-b border-[#947a4d] pb-2 text-[11px] font-black uppercase tracking-widest text-[#173b48] no-underline", children: [
            "See demonstrator inventory ",
            /* @__PURE__ */ w.jsx(p3, { className: "h-4 w-4" })
          ] })
        ] }),
        /* @__PURE__ */ w.jsx("div", { "data-editorial-gallery": "true", className: "grid gap-4 lg:grid-cols-[1.18fr_.82fr]", children: _3.map((d, p) => {
          const v = c.editorialMedia?.[p + 1], b = v || c.editorialAssetsBase + d.filename;
          return /* @__PURE__ */ w.jsxs(
            "figure",
            {
              "data-editorial-photo": d.num,
              className: "group relative isolate overflow-hidden rounded-xl bg-[#0b2029] shadow-[0_24px_55px_rgba(9,25,35,.16)] " + (p === 0 ? "min-h-[370px] lg:row-span-2 lg:min-h-[590px]" : "min-h-[290px] lg:min-h-[287px]"),
              children: [
                /* @__PURE__ */ w.jsx(
                  "img",
                  {
                    alt: v ? "Client-selected editorial automotive reference. Media rights and vehicle claims require independent review." : d.alt,
                    src: b,
                    width: d.width,
                    height: d.height,
                    loading: "lazy",
                    decoding: "async",
                    className: "absolute inset-0 h-full w-full object-cover transition-transform duration-700 motion-reduce:transition-none motion-safe:group-hover:scale-[1.035] " + (p === 2 ? "object-[center_25%]" : "object-center")
                  }
                ),
                /* @__PURE__ */ w.jsx("div", { className: "pointer-events-none absolute inset-0 bg-gradient-to-t from-[#06151f]/95 via-[#06151f]/15 to-[#06151f]/40" }),
                /* @__PURE__ */ w.jsxs("figcaption", { className: "relative z-10 flex h-full min-h-[inherit] flex-col justify-between gap-16 p-6 text-white sm:p-8", children: [
                  /* @__PURE__ */ w.jsxs("div", { className: "flex flex-wrap items-start justify-between gap-3 text-[10px] font-extrabold uppercase tracking-[.19em] text-[#f1d4a6]", children: [
                    /* @__PURE__ */ w.jsxs("span", { children: [
                      "Frame ",
                      d.num,
                      " / photographic direction"
                    ] }),
                    /* @__PURE__ */ w.jsx("span", { className: "rounded-full border border-white/25 bg-black/30 px-3 py-2 text-[9px] text-white/90 backdrop-blur-sm", children: "Editorial only" })
                  ] }),
                  /* @__PURE__ */ w.jsxs("div", { children: [
                    /* @__PURE__ */ w.jsx("h3", { className: "max-w-[20ch] font-serif leading-[1.1] tracking-[-.04em] " + (p === 0 ? "text-[clamp(2.2rem,4vw,4rem)]" : "text-[clamp(2rem,3vw,3rem)]"), children: d.name }),
                    /* @__PURE__ */ w.jsx("p", { className: "mt-2 text-sm text-slate-200", children: d.detail }),
                    /* @__PURE__ */ w.jsxs("div", { className: "mt-5 flex flex-wrap items-center gap-3 border-t border-white/20 pt-4 text-[10px] text-slate-200", children: [
                      /* @__PURE__ */ w.jsx("span", { children: "Photography reference — not a stock listing" }),
                      v ? /* @__PURE__ */ w.jsx("span", { children: "WordPress Media Library selection" }) : /* @__PURE__ */ w.jsxs(
                        "a",
                        {
                          href: d.source,
                          target: "_blank",
                          rel: "noopener noreferrer",
                          className: "pointer-events-auto text-[#efce97] underline underline-offset-4 hover:text-white focus-visible:outline-2 focus-visible:outline-white",
                          children: [
                            "Photo: ",
                            d.photographer,
                            " / Unsplash"
                          ]
                        }
                      )
                    ] })
                  ] })
                ] })
              ]
            },
            d.num
          );
        }) }),
        /* @__PURE__ */ w.jsx("p", { className: "mt-6 max-w-[83ch] text-[11px] leading-6 text-[#607178]", children: "These photographs are visual references, not inventory, customer stock, brand partnerships or claims about our fictional GT. Manufacturer names, trademarks and model rights require independent clearance for a real client deployment." })
      ] }) }),
      /* @__PURE__ */ w.jsx("section", { className: "bg-[#102832] px-5 py-20 text-white md:px-10 md:py-28", children: /* @__PURE__ */ w.jsxs("div", { className: "mx-auto flex max-w-[1240px] flex-col items-start justify-between gap-10 rounded-xl border border-[#d4ae75]/35 bg-[radial-gradient(ellipse_at_top_right,#214957_0%,#102832_50%,#091923_100%)] p-8 md:flex-row md:items-center md:p-14", children: [
        /* @__PURE__ */ w.jsxs("div", { children: [
          /* @__PURE__ */ w.jsx("p", { className: "mb-4 text-[10px] font-bold uppercase tracking-[.26em] text-[#d6b47d]", children: "A secure commercial foundation" }),
          /* @__PURE__ */ w.jsx("h2", { className: "max-w-[16ch] font-serif text-[clamp(2.7rem,4vw,4.5rem)] leading-[1.1] tracking-[-.05em]", children: "Designed to be extraordinary. Built to be responsible." }),
          /* @__PURE__ */ w.jsx("p", { className: "mt-5 max-w-[62ch] text-sm leading-[1.9] text-[#b9cbd2]", children: "Private bookings are verified in WordPress and MariaDB staging. Public booking, payments and customer enquiries remain disabled." })
        ] }),
        /* @__PURE__ */ w.jsx(bf, { primary: !0, palette: h, href: c.contact_path, children: c.contact_label })
      ] }) })
    ] }),
    /* @__PURE__ */ w.jsx("footer", { className: "border-t border-white/10 bg-[#07151f] px-5 py-12 text-[#b9c9ce] md:px-10", children: /* @__PURE__ */ w.jsxs("div", { className: "mx-auto flex max-w-[1240px] flex-col justify-between gap-6 md:flex-row", children: [
      /* @__PURE__ */ w.jsxs("div", { children: [
        /* @__PURE__ */ w.jsx("p", { className: "text-sm font-black uppercase tracking-[.2em] text-white", children: c.name }),
        /* @__PURE__ */ w.jsx("p", { className: "mt-2 max-w-[44ch] text-xs leading-7", children: "Fictional WordPress + React showroom made for internal Empire AI capability testing." })
      ] }),
      /* @__PURE__ */ w.jsxs("div", { className: "text-xs leading-7 md:text-right", children: [
        /* @__PURE__ */ w.jsx("p", { children: "No real vehicles, sales offers, reservations or customer data." }),
        /* @__PURE__ */ w.jsx("p", { children: "Client identity, privacy and commercial terms remain pending." })
      ] })
    ] }) })
  ] });
}
const yg = document.getElementById("empire-yard-react-root");
yg && dT.createRoot(yg).render(/* @__PURE__ */ w.jsx(V3, {}));
export {
  lT as R,
  uT as a,
  K as b,
  eT as g,
  w as j,
  Qf as r
};
