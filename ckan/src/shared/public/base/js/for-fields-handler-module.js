this.ckan.module('for-fields-handler-module', function ($, _) {
  return {
    initialize: function () {
      this.selectElement = $('#field-fields_of_research');
      this.codeElement = $('#field-fields_of_research_code');
      this.fetchAndPopulateTerms();
      this.selectElement.change(this.updateCodesField.bind(this));
    },

    fetchAndPopulateTerms: function() {
      var self = this;
      // Fix ORS (Cross-Origin Resource Sharing) policy error  
      fetch('https://vocabs.ardc.edu.au/viewById/316')
        .then(response => response.json())
        .then(data => {
          data.forEach(term => {
            const option = new Option(term.label, term.code);
            self.selectElement.append(option);
          });
        })
        .catch(error => console.error('Error loading FoR terms:', error));
    },

    updateCodesField: function() {
      var selectedOptions = this.selectElement.find('option:selected');
      var codes = $.map(selectedOptions, function(option) {
        return option.value;
      });

      this.codeElement.val(codes.join(', '));
    }
  };
});
