this.ckan.module('jstree-view-module', function (jquery) {
    return {
        initialize: function () {
            console.log('jQuery version:', jquery.fn.jquery); // Check jQuery version
            console.log('jsTree available:', !!jquery.fn.jstree); // Check if jsTree is a function
            this.el.ready(jquery.proxy(this.initializeTree, this));
           
        },

        initializeTree: function () {

            var self = this;
            var data = [
                { "id" : "ajson1", "parent" : "#", "text" : "Simple root node" },
                { "id" : "ajson2", "parent" : "#", "text" : "Root node 2" },
                { "id" : "ajson3", "parent" : "ajson2", "text" : "Child 1" },
                { "id" : "ajson4", "parent" : "ajson2", "text" : "Child 2" }
                ];
            jquery('#tree').jstree({
                'core' : {
                    'data' : data
                },
                'plugins' : ['types', 'wholerow'], // Optional: include plugins as needed
                'types' : {
                    'default' : {
                        'icon' : 'fa fa-folder' // Using FontAwesome icons
                    },
                    'file' : {
                        'icon' : 'fa fa-file'
                    }
        }
    });
        }
    };
});
