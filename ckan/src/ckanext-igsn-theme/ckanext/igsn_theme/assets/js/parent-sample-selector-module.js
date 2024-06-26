this.ckan.module('parent-sample-selector-module', function ($, _) {
  return {
    initialize: function () {
      this.inputElement = $('#field-parent');
      this.initializeSelect2();
      this.prepopulateSelect2();
    },

    initializeSelect2: function () {
      var self = this;
      this.org_id = this.options.group;
      console.log(self.org_id);
      this.inputElement.select2({
        placeholder: "Select Parent of Sample",
        minimumInputLength: 0,
        ajax: {
          url: '/api/3/action/organization_show',
          type: 'GET', 
          dataType: 'json',
          quietMillis: 500,
          data: function (params) {
            self.searchTerm = params || '';
            return {
              id: self.org_id,
              include_datasets: 'true'
            };
          },
          processResults: function (data) {
            if (!data.success) {
              return { results: [] };
            }
            var searchTerm = self.searchTerm.toLowerCase();
            var filteredResults = data.result.packages.filter(function (item) {
              return item.title.toLowerCase().includes(searchTerm);
            });
            return {
              results: filteredResults.map(function (item) {
                return { id: item.id, text: item.title };
              })
            };
          },
          cache: true
        },
        templateResult: function (item) { return item.text; },
        templateSelection: function (item) { return item.text; },
        dropdownCssClass: "bigdrop",
        escapeMarkup: function (m) { return m; } 
      })
    },

    prepopulateSelect2: function () {
      var self = this;
      var existingId = this.inputElement.val();
      if (existingId) {
        $.ajax({
          url: '/api/3/action/package_show',
          data: { id: existingId },
          type: 'GET',
          dataType: 'json',
          success: function (data) {
            if (data.success && data.result) {
              var item = data.result;
              var dataForSelect2 = new Option(item.title, item.id, true, true);
              self.inputElement.select2('data', dataForSelect2, true);
            }
          }
        });
      }
    }
  };
});
