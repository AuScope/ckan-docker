this.ckan.module('gcmd-fields-handler-module', function ($, _) {
  return {
    initialize: function () {
      this.selectElement = $('#field-gcmd_keywords');
      this.selectedValues = null;
      if (this.options.selectedValues === true) {
        // Already initialized as an empty set above, so do nothing
      } else {
        this.selectedValues = this.options.selectedValues;
      }

      console.log(this.selectedValues)


      this.fetchAndPopulateTerms();
    },
    fetchAndPopulateTerms: function (nextPageUrl) {
      var self = this;
      var proxyUrl = '/api/proxy/fetch_gcmd';
      var urlToFetch = nextPageUrl || proxyUrl;

      $.ajax({
        url: urlToFetch,
        method: 'GET',
        success: function (data) {
          self.populateDropdown(data.result.items);
          if (data.result.next) {
            self.fetchAndPopulateTerms(data.result.next);
          }
        },
        error: function (xhr, status, error) {
          console.error('Error fetching gcmd terms via proxy:', error);
        }
      });
    },

    populateDropdown: function (items) {
      var self = this;
      $.each(items, function (index, item) {
        var option = new Option(item.prefLabel._value, item._about);
        if (self.selectedValues && self.selectedValues.includes(item._about)) {
          option.selected = true;
          console.log(item._about)
        }
        self.selectElement.append(option);
      });
    },

  };
});
