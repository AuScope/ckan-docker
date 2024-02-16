this.ckan.module('for-fields-handler-module', function ($, _) {
  return {
    initialize: function () {
      this.selectElement = $('#field-fields_of_reserch'); 
      this.codeElement = $('#field-fields_of_research_code');
      this.fetchAndPopulateTerms();
      this.selectElement.change(this.updateCodesField.bind(this));
    },
    fetchAndPopulateTerms: function () {
      var self = this;
      // Use the proxy endpoint
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
      $.each(items, function (index, item) {
        var option = new Option(item.prefLabel._value, item.notation);
        self.selectElement.append(option);
      });
    },

    updateCodesField: function () {
      var selectedOptions = this.selectElement.val() || [];
      this.codeElement.val(selectedOptions.join(', '));
    }
  };
});
