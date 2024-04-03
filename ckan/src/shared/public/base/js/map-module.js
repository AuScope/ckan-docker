ckan.module('map-module', function ($, _) {
    return {
        initialize: function () {
            this.EPSGTextElement = $('#field-epsg');
            this.EPSGCodeElement = $('#field-epsg_code');
            this.el.ready($.proxy(this.setupMap, this));
        },

        setupMap: function () {
            var self = this;
            this.populateEPSG();
            this.prepopulateEPSG();
            this.map = L.map('map-container').setView([-31.9505, 115.8605], 3);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '© OpenStreetMap contributors'
            }).addTo(this.map);

            this.drawnItems = new L.FeatureGroup();
            this.map.addLayer(this.drawnItems);

            this.debouncedUpdateMarkerPosition = _.debounce ? _.debounce($.proxy(this.updateMarkerPosition, this), 500) : this.debounce(this.updateMarkerPosition, 500);
            this.debouncedUpdateRectangleBounds = _.debounce ? _.debounce($.proxy(this.updateRectangleBounds, this), 500) : this.debounce(this.updateRectangleBounds, 500);

            $('#field-point_latitude, #field-point_longitude').on('input', this.debouncedUpdateMarkerPosition);
            $('#field-bounding_box').on('input', this.debouncedUpdateRectangleBounds);

            this.resetMap();
            this.showMapAndInvalidate();

            var selected = $('input[type=radio][name=location_choice]:checked').val();
            if (selected == 'noLocation') {
                this.resetMap();
            }
            else if (selected == 'area') {
                this.initializeDrawControl();
                this.updateRectangleBounds(false);
                $('#bounding_box_coordinates').show();
            } else if (selected == 'point') {
                this.reinitializeMarker();
                this.addMarker();
                this.updateMarkerPosition(false);
                $('#point_latitude_container').show();
                $('#point_longitude_container').show();
                $('#elevation_container').show();
            }

            $('html,body').scrollTop(0); // Reset scroll position to the top of the page

            $('input[type=radio][name=location_choice]').change(function () {
                self.resetMap();
                self.updateLatLngFields('', '');
                self.updateBboxField('');

                var choice = $(this).val();
                if (choice == 'noLocation') {
                    // this.resetMap();
                }
                else if (choice == 'area') {
                    self.showMapAndInvalidate();
                    self.initializeDrawControl();
                    $('#bounding_box_coordinates').show();
                } else if (choice == 'point') {
                    self.showMapAndInvalidate();
                    self.reinitializeMarker();
                    $('#point_latitude_container').show();
                    $('#point_longitude_container').show();
                    $('#elevation_container').show();
                    self.addMarker();
                }
            });
            $('.card-header').on('click', '.btn-link', function () {
                setTimeout(function () {
                    if (self.map) {
                        self.map.invalidateSize();
                    }
                }, 100);
            });            
        },

        debounce: function (func, wait) {
            var self = this;
            var timeout;
            return function () {
                var context = self, args = arguments;
                clearTimeout(timeout);
                timeout = setTimeout(function () {
                    func.apply(context, args);
                }, wait);
            };
        },

        validatePointCoordinates: function (lat, lng) {
            return !isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
        },

        validateBoundingBoxCoordinates: function (bboxString) {
            if (bboxString.length !== 4 || !bboxString.every(n => !isNaN(n))) {
                return false;
            }
            var [minLng, minLat, maxLng, maxLat] = bboxString;
            var isValid = minLat >= -90 && minLat <= 90 && maxLat >= -90 && maxLat <= 90 &&
                minLng >= -180 && minLng <= 180 && maxLng >= -180 && maxLng <= 180 &&
                minLat < maxLat && minLng < maxLng;
            return isValid;
        },


        updateLatLngFields: function (lat, lng) {
            $('#field-point_latitude').val(lat);
            $('#field-point_longitude').val(lng);
        },

        updateBboxField: function (bboxString) {
            $('#field-bounding_box').val(bboxString);
        },

        resetMap: function () {
            this.drawnItems.clearLayers();
            this.map.removeLayer(this.drawnItems);
            this.map.off('click');
            if (this.drawControl) {
                this.map.removeControl(this.drawControl);
            }
            if (this.marker) {
                this.map.removeLayer(this.marker);
                this.marker = null;
            }
            $('#point_latitude_container').hide();
            $('#point_longitude_container').hide();
            $('#elevation_container').hide();
            $('#bounding_box_coordinates').hide();
            $('#map-container').hide();
            $('#epsg_code_container').hide();
        },

        showMapAndInvalidate: function () {
            $('#map-container').show();
            $('#epsg_code_container').show();
            var self = this;
            setTimeout(function () {

                if (self.map) {
                    self.map.invalidateSize();
                }
            }, 100);
        },
        initializeDrawControl: function () {
            this.map.addLayer(this.drawnItems);
            if (!this.drawControl) {
                this.drawControl = new L.Control.Draw({
                    draw: {
                        polygon: false,
                        marker: false,
                        circlemarker: false,
                        circle: false,
                        polyline: false,
                        rectangle: true
                    },
                    edit: {
                        featureGroup: this.drawnItems,
                        edit: false,
                        remove: false
                    }
                });
            }
            this.map.addControl(this.drawControl);

            if (!this.rectangleDrawer) {
                this.rectangleDrawer = new L.Draw.Rectangle(this.map, this.drawControl.options.draw.rectangle);
            }
            this.rectangleDrawer.enable();

            var self = this;
            this.map.on(L.Draw.Event.CREATED, function (event) {
                var layer = event.layer;
                self.drawnItems.clearLayers();
                self.drawnItems.addLayer(layer);
                var bounds = layer.getBounds();
                self.updateBboxField(bounds.toBBoxString());
            });


        },

        reinitializeMarker: function () {
            if (this.rectangleDrawer) {
                this.rectangleDrawer.disable();
            }

        },

        addMarker: function () {
            var self = this;

            this.map.off('click').on('click', function (e) {
                if (!self.marker) {
                    self.marker = L.marker(e.latlng, { draggable: true }).addTo(self.map);
                    self.marker.on('dragend', function (event) {
                        var marker = event.target;
                        var position = marker.getLatLng();
                        self.updateLatLngFields(position.lat, position.lng);
                    });
                } else {
                    self.marker.setLatLng(e.latlng);
                }
                self.updateLatLngFields(e.latlng.lat, e.latlng.lng);
            });
        },


        updateMarkerPosition: function (checkValidity = true) {
            var lat = parseFloat($('#field-point_latitude').val());
            var lng = parseFloat($('#field-point_longitude').val());
            if (this.validatePointCoordinates(lat, lng)) {
                var newLatLng = new L.LatLng(lat, lng);
                if (this.marker) {
                    this.marker.setLatLng(newLatLng);
                } else {
                    this.marker = L.marker(newLatLng, { draggable: true }).addTo(this.map);
                }

                this.map.panTo(newLatLng);
            } else if (checkValidity && !this.validatePointCoordinates(lat, lng)) {
                alert("Invalid point coordinates. Latitude must be between -90 and 90, Longitude between -180 and 180.");
            }
        },


        updateRectangleBounds: function (checkValidity = true) {
            var bboxString = $('#field-bounding_box').val().split(',').map(Number);
            if (this.validateBoundingBoxCoordinates(bboxString)) {
                var southWest = L.latLng(bboxString[1], bboxString[0]);
                var northEast = L.latLng(bboxString[3], bboxString[2]);
                var bounds = L.latLngBounds(southWest, northEast);

                this.drawnItems.clearLayers();

                L.rectangle(bounds, { color: "#ff7800", weight: 1 }).addTo(this.drawnItems);

            } else if (checkValidity && !this.validateBoundingBoxCoordinates(bboxString)) {
                alert("Invalid bounding box coordinates. Please enter valid latitudes and longitudes.");
            }
        },

        populateEPSG: function () {
            var self = this;
            var nextPage = 0;
            var lastSearchTerm = null;

            self.EPSGCodeElement.select2({
                placeholder: 'Search for an EPSG code',
                minimumInputLength: 0,
                delay: 250,
                cache: true,
                query: function (query) {
                    if (lastSearchTerm !== query.term) {
                        nextPage = 0; 
                        lastSearchTerm = query.term; 
                    }
                    var apiUrl = '/api/proxy/fetch_epsg';
                    var data = {
                        page: nextPage, 
                        keywords: query.term 
                    };

                    $.ajax({
                        type: 'GET',
                        url: apiUrl,
                        data: data, 
                        dataType: 'json',
                        success: function (data) {
                            var filteredItems = data.Results.filter(function (item) {
                                return item.Type === 'geographic 2D' || item.Type === 'compound';
                            }).map(function (item) {
                                return { id: item.Code, text: item.Code + ' - ' + item.Name };
                            });
                            nextPage = data.Page + 1;
                            query.callback({
                                results: filteredItems,
                                more: ((data.Page * data.PageSize) < data.TotalResults)
                            });
                        }
                    });
                }
            }).on("change", function (e) {
                self.updateDependentFields();
            });

        },

        updateDependentFields: function () {
            var self = this;
            var selectedData = self.EPSGCodeElement.select2('data');
            self.EPSGTextElement.val(selectedData.text);
        },

        prepopulateEPSG: function () {
            var self = this;
            var existingId = this.EPSGCodeElement.val();
            var existingText = this.EPSGTextElement.val();
            if (existingId && existingId !=="" ) {
                var dataForSelect2 =  { id: existingId, text: existingText };
                self.EPSGCodeElement.select2('data', dataForSelect2, true);
            }
        },

    };
});
