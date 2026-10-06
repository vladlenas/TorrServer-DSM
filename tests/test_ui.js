// Tests for src/ui/TorrServer.js (the DSM desktop app). No DSM needed.
// Run:  node tests/test_ui.js
"use strict";
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "..", "src", "ui", "TorrServer.js"), "utf8");

// A minimal stand-in for the parts of ExtJS / DSM the file touches.
function load(env) {
    env = env || {};
    const logs = [];
    const frames = {};
    const requests = [];
    const defined = {};

    const Ext = {
        namespace(name) {
            name.split(".").reduce((o, k) => (o[k] = o[k] || {}), sandbox);
        },
        apply(target, source) { return Object.assign(target, source); },
        define(name, cfg) { defined[name] = cfg; },
        decode: JSON.parse,
        getDom(id) { return frames[id]; },
        Ajax: {
            defaultHeaders: env.defaultHeaders,
            extraParams: env.extraParams,
            request(options) {
                requests.push(options);
                if (env.login === "throw") { throw new Error("boom"); }
                setImmediate(() => {
                    if (env.login === "fail") { options.failure(); }
                    else if (env.login !== undefined) { options.success({ responseText: env.login }); }
                });
            },
        },
    };
    const sandbox = {
        Ext,
        SYNO: { SDS: { Session: env.session } },
        window: { console: { log: (m) => logs.push(m) }, SynoToken: env.windowToken },
        console: { log: (m) => logs.push(m) },
        encodeURIComponent, JSON, setImmediate,
    };
    vm.createContext(sandbox);
    vm.runInContext(SOURCE, sandbox);
    frames["torrserver-helper-frame"] = { src: "" };
    return { sandbox, utils: sandbox.SYNO.SDS.TorrServer.Utils, frame: frames["torrserver-helper-frame"], logs, requests, defined };
}

let failed = 0;
async function test(name, fn) {
    try { await fn(); console.log("PASS " + name); }
    catch (e) { failed++; console.log("FAIL " + name + "\n     " + e.message); }
}
const loadHelper = (ctx) => new Promise((resolve) => {
    ctx.utils.loadHelper();
    setTimeout(resolve, 20);
});

(async () => {
    await test("frame starts empty so nothing loads before the token is known", () => {
        const { utils } = load({});
        const html = utils.getMainHtml();
        assert(html.includes('id="torrserver-helper-frame"'));
        assert(!/\ssrc=/.test(html), "iframe must not have a src yet");
    });

    await test("token from SYNO.SDS.Session is used first", async () => {
        const ctx = load({ session: { SynoToken: "SESSIONTOK" }, defaultHeaders: { "X-SYNO-TOKEN": "HEADERTOK" } });
        await loadHelper(ctx);
        assert.strictEqual(ctx.frame.src, "/webman/3rdparty/TorrServer/helper/?SynoToken=SESSIONTOK");
        assert(ctx.logs.some((l) => l.includes("SYNO.SDS.Session.SynoToken")));
        assert.strictEqual(ctx.requests.length, 0, "no network request needed");
    });

    await test("falls back to the X-SYNO-TOKEN header DSM sets on Ext.Ajax", async () => {
        const ctx = load({ session: {}, defaultHeaders: { "X-SYNO-TOKEN": "HEADERTOK" } });
        await loadHelper(ctx);
        assert(ctx.frame.src.endsWith("?SynoToken=HEADERTOK"));
    });

    await test("falls back to Ext.Ajax.extraParams and window.SynoToken", async () => {
        let ctx = load({ extraParams: { SynoToken: "PARAMTOK" } });
        await loadHelper(ctx);
        assert(ctx.frame.src.endsWith("?SynoToken=PARAMTOK"));
        ctx = load({ windowToken: "WINTOK" });
        await loadHelper(ctx);
        assert(ctx.frame.src.endsWith("?SynoToken=WINTOK"));
    });

    await test("asks DSM for the token when nothing is stored in the page", async () => {
        const ctx = load({ login: JSON.stringify({ success: true, SynoToken: "REMOTETOK" }) });
        await loadHelper(ctx);
        assert.strictEqual(ctx.requests[0].url, "/webman/login.cgi");
        assert.strictEqual(ctx.requests[0].method, "GET");
        assert(ctx.frame.src.endsWith("?SynoToken=REMOTETOK"));
        assert(ctx.logs.some((l) => l.includes("/webman/login.cgi")));
    });

    await test("token is URL-encoded", async () => {
        const ctx = load({ session: { SynoToken: "a b&c=d/+" } });
        await loadHelper(ctx);
        assert(ctx.frame.src.endsWith("?SynoToken=a%20b%26c%3Dd%2F%2B"));
    });

    await test("still loads the helper (which will refuse) when no token can be found", async () => {
        for (const login of ["fail", "throw", "not json", JSON.stringify({ success: false })]) {
            const ctx = load({ login });
            await loadHelper(ctx);
            assert.strictEqual(ctx.frame.src, "/webman/3rdparty/TorrServer/helper/", "login=" + login);
            assert(ctx.logs.some((l) => l.includes("not found")));
        }
    });

    await test("non-string or empty tokens are ignored", async () => {
        const ctx = load({ session: { SynoToken: 12345 }, defaultHeaders: { "X-SYNO-TOKEN": "" }, login: JSON.stringify({ SynoToken: "OK" }) });
        await loadHelper(ctx);
        assert(ctx.frame.src.endsWith("?SynoToken=OK"));
    });

    await test("opening the window loads the helper after the frame is rendered", async () => {
        const ctx = load({ session: { SynoToken: "WINTOK" } });
        const Win = ctx.defined["SYNO.SDS.TorrServer.MainWindow"];
        assert(Win && typeof Win.constructor === "function", "MainWindow is defined");

        // Run the real constructor against a fake window object.
        const handlers = [];
        const fakeWindow = { on(event, fn, scope, opts) { handlers.push({ event, fn, scope, opts }); } };
        const MY = vm.runInContext("SYNO.SDS.TorrServer", ctx.sandbox);
        MY.MainWindow = { superclass: { constructor() { MY.superCalled = true; } } };
        Win.constructor.call(fakeWindow, {});

        assert(MY.superCalled, "parent constructor ran");
        assert.strictEqual(ctx.frame.src, "", "nothing is loaded before the window is rendered");
        const hook = handlers.find((h) => h.event === "afterrender");
        assert(hook, "an afterrender handler is registered");
        assert(hook.opts && hook.opts.single, "and it only fires once");

        hook.fn.call(hook.scope);
        await new Promise((r) => setTimeout(r, 20));
        assert.strictEqual(ctx.frame.src, "/webman/3rdparty/TorrServer/helper/?SynoToken=WINTOK");
    });

    console.log(failed ? "\nFAILED: " + failed : "\nALL PASSED");
    process.exit(failed ? 1 : 0);
})();
