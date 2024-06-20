ckan.module('datatable-module', function ($, _) {
    return {
        initialize: function () {
            var endpoint = this.el.data('endpoint');
            this.fetchPreviewData(endpoint);
        },
        fetchPreviewData: function (endpoint) {
            $.ajax({
                url: endpoint,
                success: function (data) {
                    this.setupTable(data);
                }.bind(this),
                error: function (xhr, status, error) {
                    console.error('Failed to fetch preview data:', error);
                }
            });
        },
        setupTable: function (preview_data) {
            var authorsData = preview_data.authors;
            var resourcesData = preview_data.related_resources;
            var samplesData = preview_data.samples;
            sampleExcludedColumns = ["owner_org", "notes", "location_data", "location_choice", "related_resources_urls", "author_emails"];
            sampleJsonColumns = ['author', 'related_resource'];
            sampleJsonColumnsTitle = ['author_name', 'related_resource_title'];
            this.setupDataTable('#authorsTable', authorsData);
            this.setupDataTable('#resourcesTable', resourcesData);
            this.setupDataTable('#samplesTable', samplesData, true, sampleExcludedColumns, sampleJsonColumns, sampleJsonColumnsTitle);
            $('.collapsible-header').click(function () {
                $(this).next('.collapsible-content').slideToggle();
            });
        },

        setupDataTable: function (selector, data, addStyle = false, excludedColumns = [], jsonColumns = [], jsonColumnsTitle = []) {
            var self = this;
            if (data && data.length > 0) {
                var columns = Object.keys(data[0]).filter(function (key) {
                    return !excludedColumns.includes(key);
                }).map(function (key) {
                    return { title: key.charAt(0).toUpperCase() + key.slice(1), data: key };
                });

                var columnDefs = columns.map(function (column, index) {
                    if (jsonColumns.includes(column.data)) {
                        var jsonColumnIndex = jsonColumns.indexOf(column.data);
                        return {
                            targets: index,
                            render: function (data, type, row, meta) {
                                return type === 'display' ?
                                    self.renderDisplay(data, jsonColumnsTitle[jsonColumnIndex]) :
                                    data;
                            }
                        };
                    } else {
                        return {
                            targets: index,
                            render: function (data, type, row, meta) {
                                $(row).addClass('row-success');

                                if (type === 'display') {
                                    return '<div class="cell-wrap" title="' + data + '">' + data + '</div>';
                                }
                                return data;
                            }
                        };
                    }
                });

                var table = $(selector).DataTable({
                    data: data,
                    columns: columns,
                    responsive: true,
                    scrollY: 800,
                    scrollCollapse: true,
                    scroller: true,
                    lengthChange: false,
                    searching: false,
                    columnDefs: columnDefs,
                });
                if (addStyle) {
                    self.addStatusClasses(table);
                    table.on('draw.dt', function () {
                        self.addStatusClasses(table);
                    });
                }
            }
        },
        renderDisplay: function (data, colName) {
            var objectArray = JSON.parse(data);
            var formattedObject = '<div class="collapsible-container">';
            objectArray.forEach(function (object, index) {
                var name = object[colName] || (index + 1);
                formattedObject += '<div class="collapsible-header">' + '<a href="#" class="author-link">' + name + '</a>' + '</div>';
                formattedObject += '<div class="collapsible-content">';
                Object.keys(object).forEach(function (key) {
                    formattedObject += '<strong>' + key + ':</strong> ' + object[key] + '<br>';
                });
                formattedObject += '</div>';
            });
            formattedObject += '</div>'; 
            return '<div class="cell-wrap">' + formattedObject + '</div>';
        },

        addStatusClasses: function (table) {
            table.rows().every(function (rowIdx, tableLoop, rowLoop) {
                var rowData = this.data();
                if (rowData.status !== undefined) {
                    var rowNode = this.node();
                    if (rowData.status === 'created') {
                        $(rowNode).addClass('row-success');
                    }
                    if (rowData.status === 'error') {
                        $(rowNode).addClass('row-error');
                    }
                }
            });
        },
    }
});