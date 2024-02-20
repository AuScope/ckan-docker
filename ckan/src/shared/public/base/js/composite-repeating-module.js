ckan.module('composite-repeating-module', function ($, _) {
  return {
    initialize: function () {
      this.updateCollapsiblePanels();
      this.updateIndexes();
      var self = this;

      $(document).on('click', '.composite-btn.btn-success, .composite-btn.btn-danger', function () {
        setTimeout(function () {
          self.updateIndexes();
          self.updateCollapsiblePanels();
        }, 100);
      });

      // this.setupAffiliationAutocomplete();
      this.setupAffiliationListener();
    },

    setupAffiliationAutocomplete: function() {
          var self = this;
          $('input[id*="author-"][id*="-author_affiliation"]').autocomplete({
            source: function(request, response) {
              $.ajax({
                url: `https://api.ror.org/organizations?query=${encodeURIComponent(request.term)}`,
                type: 'GET',
                success: function(data) {
                  response($.map(data.items, function(item) {
                    return {
                      label: item.name, // Label for displaying in the suggestions
                      value: item.name, // Value to be inserted in the input field
                      id: item.id // ROR ID to use for the affiliation identifier
                    };
                  }));
                },
                error: function() {
                  response([]);
                }
              });
            },
            minLength: 3, 
            select: function(event, ui) {
              var $inputField = $(this);

              var identifierFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier');
              $('#' + identifierFieldId).val(ui.item.id);

              // Update the identifier type field to 'ror'
              var identifierTypeFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier_type');
              $('#' + identifierTypeFieldId).val('ror');

              self.manageFieldsReadonly(true);
            }
          });
    
    },
    setupAffiliationListener: function () {
      var self = this;
      $(document).on('input', 'input[id*="author-"][id*="-author_affiliation"]', function () {
        var affiliationName = $(this).val();
        if (affiliationName.length === 0) {
          self.clearDependentFields($(this));
        } else if (affiliationName.length > 3) { // Continue with the API call if there's sufficient input
          self.fetchAffiliationData(affiliationName, $(this));
        }
      });
    },
    clearDependentFields: function ($inputField) {
      // Construct the IDs for the dependent fields based on the input field's ID
      var identifierFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier');
      var identifierTypeFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier_type');

      // Clear the values of the dependent fields
      $('#' + identifierFieldId).val('');
      $('#' + identifierTypeFieldId).val('');

      this.manageFieldsReadonly(false);
    },

    fetchAffiliationData: function (affiliationName, $inputField) {
      var self = this;
      $.ajax({
        url: `https://api.ror.org/organizations?query=${encodeURIComponent(affiliationName)}`,
        type: 'GET',
        success: function (data) {
          if (data && data.items.length > 0) {
            const firstResult = data.items[0];
            var identifierFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier');
            $('#' + identifierFieldId).val(firstResult.id);

            var identifierTypeFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier_type');
            $('#' + identifierTypeFieldId).val('ror');
            self.manageFieldsReadonly(true);
          } else {
            self.clearDependentFields($inputField);
          }
        },
        error: function (xhr, status, error) {
          self.clearDependentFields($inputField);
          console.error('Error fetching ROR data:', error);
        }
      });
    },

    hideDependentFields: function () {
      $('input[id*="author-"][id*="-author_affiliation"]:not([id*="identifier"])').each(function () {
        var $inputField = $(this);

        var identifierFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier');
        var $identifierFieldGroup = $('#' + identifierFieldId).closest('.form-group');
        $identifierFieldGroup.hide();

        var identifierTypeFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier_type');
        var $identifierTypeFieldGroup = $('#' + identifierTypeFieldId).closest('.form-group');
        $identifierTypeFieldGroup.hide();
      });
    },

    manageFieldsReadonly: function (readonly) {
      $('input[id*="author-"][id*="-author_affiliation"]:not([id*="identifier"])').each(function () {
        var $inputField = $(this);

        // Construct the IDs for the dependent fields based on the input field's ID
        var identifierFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier');
        var identifierTypeFieldId = $inputField.attr('id').replace('affiliation', 'affiliation_identifier_type');

        // Make the dependent fields readonly instead of hiding them
        $('#' + identifierFieldId).prop('readonly', readonly).closest('.form-group').show(); // Show the group and make field readonly
        $('#' + identifierTypeFieldId).prop('readonly', readonly).closest('.form-group').show(); // Show the group and make field readonly
      });
    },

    makeCollapsible: function (title, groups) {
      var self = this;
      groups.forEach(function (group, index) {
        let panelHeader = group.querySelector('.composite-panel-header');
        let contentWrapper = group.querySelector('.composite-content');
        self.updatePanelHeader(group, panelHeader, contentWrapper, title, index);
      });
    },

    updatePanelHeader: function (group, panelHeader, contentWrapper, title, index) {
      if (!contentWrapper) {
        contentWrapper = document.createElement('div');
        contentWrapper.className = 'composite-content active';
        Array.from(group.childNodes).forEach(function (child) {
          if (child !== panelHeader) contentWrapper.appendChild(child.cloneNode(true));
        });
        while (group.firstChild) group.removeChild(group.firstChild);
        if (panelHeader) group.appendChild(panelHeader);
        group.appendChild(contentWrapper);
      }

      if (panelHeader) {
        let headerText = panelHeader.querySelector('span:last-child'); // Assuming the last span is the headerText
        if (!headerText) {
          headerText = document.createElement('span');
          panelHeader.appendChild(headerText);
        }
        headerText.textContent = 'Details of ' + title + ' ' + (index + 1);
      } else {
        // If somehow there's no panelHeader, create it anew (might be unlikely if cloning behavior is consistent)
        panelHeader = document.createElement('div');
        panelHeader.className = 'composite-panel-header';
        const toggleIndicator = document.createElement('span');
        toggleIndicator.className = 'toggle-indicator';
        toggleIndicator.textContent = '▼';
        const headerText = document.createElement('span');
        headerText.textContent = 'Details of ' + title + ' ' + (index + 1);
        panelHeader.appendChild(toggleIndicator);
        panelHeader.appendChild(headerText);
        group.insertBefore(panelHeader, group.firstChild);
      }
      const panelHeaderClone = panelHeader.cloneNode(true);
      panelHeader.parentNode.replaceChild(panelHeaderClone, panelHeader);

      panelHeaderClone.addEventListener('click', function () {
        contentWrapper.classList.toggle('active');
        const indicator = panelHeaderClone.querySelector('.toggle-indicator');
        indicator.textContent = contentWrapper.classList.contains('active') ? '▲' : '▼';
      });
    },

    updateCollapsiblePanels: function () {
      var self = this;
      $(document).find('[data-module="composite-repeating"]').each(function () {
        var title = $(this).closest('[data-module="composite-repeating-module"]').find('.hidden-title-input').val() || 'Default Title';
        const groups = this.querySelectorAll('.composite-control-repeating');
        self.makeCollapsible(title, groups);
      });
    },

    updateIndexes: function () {
      $(document).find('[data-module="composite-repeating"]').each(function () {
        $(this).find('.composite-control-repeating').each(function (index, item) {
          $(item).find('label, input, select').each(function () {
            if (this.tagName === 'LABEL' && this.htmlFor) {
              const newFor = this.htmlFor.replace(/\d+/, index + 1);
              this.htmlFor = newFor;
              const matches = this.textContent.match(/(.*?)(\d+)$/);
              if (matches && matches.length > 2) {
                this.textContent = `${matches[1]}${index + 1}`;
              }
            }

            if (this.tagName === 'INPUT' || this.tagName === 'SELECT') {
              const baseId = this.id.replace(/\d+/, index + 1);
              this.id = baseId;
              const baseName = this.name.replace(/\d+/, index + 1);
              this.name = baseName;
            }
          });
        });
      });
    }
  };
});
