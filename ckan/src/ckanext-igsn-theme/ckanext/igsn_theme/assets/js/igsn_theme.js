ckan.module("igsn_theme", function ($, _) {
  "use strict";
  return {
    options: {
      debug: false,
    },

    initialize: function () {
        console.log("Initialized!");
    },
  };
});
