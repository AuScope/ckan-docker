this.ckan.module('for-fields-handler-module', function ($, _) {
  return {
    initialize: function () {
      this.selectElement = $('#field-fields_of_research');
      this.codeElement = $('#field-fields_of_research_code');
      this.fetchAndPopulateTerms();
      this.selectElement.change(this.updateCodesField.bind(this));
    },

    fetchAndPopulateTerms: function () {
      var self = this;
      var proxyUrl = '/api/proxy/fetch_terms';
      $.ajax({
        url: proxyUrl,
        method: 'GET',
        success: function (data) {
          self.populateDropdown(data.result.items);

        },
        error: function (xhr, status, error) {
          console.error('Error fetching FoR terms via proxy:', error);
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
        var option = new Option(item.prefLabel._value, item.notation);
        if (selectedValues.includes(item.notation.toString())) {
          option.selected = true;
        }
        self.selectElement.append(option);
      });
    },


    updateCodesField: function () {
      var selectedOptions = this.selectElement.val() || [];
      this.codeElement.val(selectedOptions.join(', '));
    }
  };
});
