Ext.namespace("SYNO.SDS.TorrServer.Utils");

Ext.apply(SYNO.SDS.TorrServer.Utils, function() {
    var HELPER_URL = "/webman/3rdparty/TorrServer/helper/";
    var FRAME_ID = "torrserver-helper-frame";

    function log(message) {
        try {
            if (window.console && window.console.log) {
                window.console.log("[TorrServer] " + message);
            }
        } catch (e) {
            /* ignore */
        }
    }

    // The helper only serves DSM administrators. It verifies the DSM session
    // with authenticate.cgi, which refuses a session without its CSRF token
    // (SynoToken). Look for the token in the places DSM keeps it.
    function findTokenSync() {
        var sources = [
            ["SYNO.SDS.Session.SynoToken", function() {
                return SYNO.SDS.Session.SynoToken;
            }],
            ["Ext.Ajax.defaultHeaders", function() {
                return Ext.Ajax.defaultHeaders["X-SYNO-TOKEN"];
            }],
            ["Ext.Ajax.extraParams", function() {
                return Ext.Ajax.extraParams.SynoToken;
            }],
            ["window.SynoToken", function() {
                return window.SynoToken;
            }]
        ];

        for (var i = 0; i < sources.length; i++) {
            try {
                var value = sources[i][1]();
                if (typeof value === "string" && value) {
                    return {token: value, source: sources[i][0]};
                }
            } catch (e) {
                /* source not available in this DSM version */
            }
        }

        return null;
    }

    // Last resort: a logged-in session can ask DSM for its own token.
    function findTokenRemote(done) {
        try {
            Ext.Ajax.request({
                url: "/webman/login.cgi",
                method: "GET",
                timeout: 8000,
                success: function(response) {
                    var token = "";
                    try {
                        token = Ext.decode(response.responseText).SynoToken || "";
                    } catch (e) {
                        token = "";
                    }
                    done(token ? {token: token, source: "/webman/login.cgi"} : null);
                },
                failure: function() {
                    done(null);
                }
            });
        } catch (e) {
            done(null);
        }
    }

    function resolveToken(done) {
        var found = findTokenSync();

        if (found) {
            done(found);
            return;
        }

        findTokenRemote(done);
    }

    function helperSrc(found) {
        return HELPER_URL +
            (found ? "?SynoToken=" + encodeURIComponent(found.token) : "");
    }

    return {
        findTokenSync: findTokenSync,
        resolveToken: resolveToken,
        helperSrc: helperSrc,

        // The frame starts empty; loadHelper() points it at the helper as
        // soon as the token is known.
        getMainHtml: function() {
            return '<iframe id="' + FRAME_ID + '" ' +
                'title="TorrServer Helper" ' +
                'style="width:100%;height:100%;border:0;margin:0;padding:0;display:block;" ' +
                'frameborder="0"></iframe>';
        },

        loadHelper: function() {
            resolveToken(function(found) {
                var frame = Ext.getDom(FRAME_ID);

                log(found ?
                    "SynoToken found via " + found.source :
                    "SynoToken not found; the helper will refuse access");

                if (frame) {
                    frame.src = helperSrc(found);
                }
            });
        }
    };
}());

Ext.define("SYNO.SDS.TorrServer.Application", {
    extend: "SYNO.SDS.AppInstance",
    appWindowName: "SYNO.SDS.TorrServer.MainWindow",

    constructor: function() {
        this.callParent(arguments);
    }
});

Ext.define("SYNO.SDS.TorrServer.MainWindow", {
    extend: "SYNO.SDS.AppWindow",

    constructor: function(cfg) {
        var MY = SYNO.SDS.TorrServer;

        this.appInstance = cfg && cfg.appInstance;

        MY.MainWindow.superclass.constructor.call(this, Ext.apply({
            layout: "fit",
            resizable: true,
            maximizable: true,
            minimizable: true,
            width: 1100,
            height: 760,
            minWidth: 800,
            minHeight: 550,
            title: "TorrServer DSM",
            html: MY.Utils.getMainHtml()
        }, cfg));

        MY.Utils.ApplicationWindow = this;

        this.on("afterrender", function() {
            MY.Utils.loadHelper();
        }, this, {single: true});
    },

    onOpen: function() {
        SYNO.SDS.TorrServer.MainWindow.superclass.onOpen.apply(
            this,
            arguments
        );
    },

    onRequest: function(request) {
        SYNO.SDS.TorrServer.MainWindow.superclass.onRequest.call(
            this,
            request
        );
    },

    onClose: function() {
        SYNO.SDS.TorrServer.MainWindow.superclass.onClose.apply(
            this,
            arguments
        );

        this.doClose();
        return true;
    }
});
