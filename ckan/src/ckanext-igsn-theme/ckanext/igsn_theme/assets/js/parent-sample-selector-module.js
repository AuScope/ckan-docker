this.ckan.module('parent-sample-selector-module', function ($, _) {
  return {
    initialize: function () {
      this.textInputElement = $('#field-parent-name');
      this.inputElement = $('#field-parent');
      this.initializeSelect2();
      this.prepopulateSelect2();
    },

    initializeSelect2: function () {
      var self = this;

      this.inputElement.select2({
        placeholder: "Select Parent of Sample",
        minimumInputLength: 3,
        ajax: {
          url: '/api/3/action/package_search',
          dataType: 'json',
          quietMillis: 500,
          data: function (term, page) {
            return {
              q: term,
              include_private: true
            };
          },
          results: function (data, page) {
            if (!data.success) {
              return { results: [] };
            }
            return {
              results: data.result.results.map(function (item) {
                return { id: item.id, text: item.title };
              })
            };
          },
          cache: true
        },
        formatResult: function (item) { return item.text; },
        formatSelection: function (item) { return item.text; },
        dropdownCssClass: "bigdrop",
        escapeMarkup: function (m) { return m; } // we do not want to escape markup since we are displaying html in results
      }).on("change", function (e) {
        self.updateDependentFields();
      });
    },
    updateDependentFields: function () {
      var self = this;

      var selectedData = self.inputElement.select2('data');
      if (selectedData) {
        self.textInputElement.val(selectedData.text);
      }
    },

    prepopulateSelect2: function () {
      var self = this;
      var existingId = this.inputElement.val();
      var existingText = this.textInputElement.val(); // Assuming you store the selected text in data attribute

      if (existingId && existingText) {
        var dataForSelect2 = { id: existingId, text: existingText };
        self.inputElement.select2('data', dataForSelect2, true);
      }
    }
  };
});
