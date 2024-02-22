this.ckan.module('gcmd-fields-handler-module', function ($, _) {
  return {
    initialize: function () {
      this.selectElement = $('#field-gcmd_keywords');
      this.fetchAndPopulateTerms();
    },

    fetchAndPopulateTerms: function () {
      var self = this;
      var proxyUrl = '/api/proxy/fetch_gcmd';
      $.ajax({
        url: proxyUrl,
        method: 'GET',
        success: function (data) {
          self.populateDropdown(data.result.items);

        },
        error: function (xhr, status, error) {
          console.error('Error fetching gcmd terms via proxy:', error);
        }
      });
    },
    populateDropdown: function (items) {
      var self = this;
      var selectedValues = this.options.selectedValues;
      if (typeof selectedValues === 'string') {
        selectedValues = selectedValues.replace(/^\{|\}$/g, '').split(',');
      } else if (typeof selectedValues === 'number') {
        selectedValues = [selectedValues.toString()];
      } else {
        selectedValues = [];
      }
      selectedValues = selectedValues.map(function (value) {
        return value.trim();
      });

      $.each(items, function (index, item) {
        var option = new Option(item.prefLabel._value, item._about);
        if (selectedValues.includes(item._about)) {
          option.selected = true;
        }
        self.selectElement.append(option);
      });
    },

  };
});
