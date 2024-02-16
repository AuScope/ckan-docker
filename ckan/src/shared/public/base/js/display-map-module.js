ckan.module('display-map-module', function ($, _) {
    return {
        initialize: function () {
            this.el.ready($.proxy(this.setupMap, this));
        },

        setupMap: function () {
            var pointLat = this.el.data('point-lat');
            var pointLong = this.el.data('point-long');
            var boundingBox = this.el.data('bounding-box');

            if (pointLat && pointLong) {
                this.initializeMapWithPoint(pointLat, pointLong);
            } else if (boundingBox) {
                var bboxValues = boundingBox.split(',').map(function (item) { return parseFloat(item.trim()); });
                if (bboxValues.length === 4) {
                    this.initializeMapWithBoundingBox(bboxValues);
                }
            }
        },

        initializeMapWithPoint: function (lat, lng) {
            var map = L.map('map-container').setView([lat, lng], 3);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
                maxZoom: 19,
            }).addTo(map);
            L.marker([lat, lng]).addTo(map);

            $('#location-info').text('Latitude: ' + lat + ', Longitude: ' + lng);

        },


        initializeMapWithBoundingBox: function (bbox) {
            var map = L.map('map-container').fitBounds([
                [bbox[1], bbox[0]], // [minLatitude, minLongitude]
                [bbox[3], bbox[2]]  // [maxLatitude, maxLongitude]
            ]);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
                maxZoom: 19,
            }).addTo(map);
            var centerLat = (bbox[1] + bbox[3]) / 2;
            var centerLng = (bbox[0] + bbox[2]) / 2;
            map.fitBounds([
                [bbox[1], bbox[0]],
                [bbox[3], bbox[2]]
            ]);
            map.setView([centerLat, centerLng], 3);
            var bounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]];
            L.rectangle(bounds).addTo(map);

            $('#location-info').html('Bounding Box: ' + bbox.join(', '));

        }
    };
});