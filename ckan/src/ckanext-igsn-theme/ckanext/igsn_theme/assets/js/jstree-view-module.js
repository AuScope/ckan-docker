this.ckan.module('jstree-view-module', function (jquery) {
    return {
        initialize: function () {
            this.el.ready(jquery.proxy(this.initializeTree, this));
        },

        initializeTree: function () {
            var self = this;
            var id = this.el.attr('data-id');
            var title = this.el.attr('data-title');

            var data = [{
                "text": title,
                "id": id,
                "state": {
                    "opened": true
                }
            }];

            $('#tree').jstree({
                'core': {
                    'data': data,
                    'check_callback': true,
                    'themes': {
                        'theme': 'proton',
                        'responsive': true
                    }
                },
                'plugins': ['types', 'wholerow'],
                'types': {
                    'default': {
                        'icon': 'fa fa-folder'
                    },
                    'branch': {
                        'icon': 'fa fa-folder'
                    },
                    'leaf': {
                        'icon': 'fa fa-file'
                    }
                }
            }).on("select_node.jstree", function (e, data) {
                if (data.node.children.length === 0) {
                    self.fetchChildren(data.node.id);
                }
            });
            
            $('#tree').on("dblclick", ".jstree-anchor", function (e) {
                var href = $(this).attr('href');
                if (href) {
                    e.preventDefault();
                    window.location.href = href;
                }
            });

        self.fetchChildren(id);

        },

        fetchChildren: function (packageId) {
            var self = this;
            $.ajax({
                url: '/api/3/action/package_relationships_list',
                method: 'GET',
                data: { id: packageId, rel: 'parent_of' },
                success: function (response) {
                    if (response.success && response.result.length > 0) {
                        var childProcessor = self.createChildProcessor(packageId);
                        childProcessor.processChildren(response.result);
                    } else {
                        $('#tree').jstree(true).set_type(packageId, "leaf");
                    }
                },
                error: function (xhr) {
                    console.error('Error fetching children:', xhr.statusText);
                    $('#tree').jstree(true).set_type(packageId, "leaf");
                }
            });
        },

        createChildProcessor: function (packageId) {
            var childrenCount;
            var checkedChildren = [];

            function verifyChild(child) {
                $.ajax({
                    url: '/api/3/action/package_show',
                    data: { id: child.id },
                    method: 'GET',
                    success: function (detailResponse) {
                        if (detailResponse.success && detailResponse.result.state === 'active') {
                            checkedChildren.push(child);
                        }
                        updateTree();
                    },
                    error: function () {
                        console.error('Error fetching details for child:', child.id);
                        updateTree();
                    }
                });
            }

            function updateTree() {
                if (--childrenCount === 0) {
                    if (checkedChildren.length > 0) {
                        checkedChildren.forEach(function (validChild) {
                            $('#tree').jstree(true).create_node(packageId, validChild, "last");
                            $('#tree').jstree(true).open_node(packageId);
                        });
                        $('#tree').jstree(true).set_type(packageId, "branch");
                    } else {
                        $('#tree').jstree(true).set_type(packageId, "leaf");
                    }
                }
            }

            return {
                processChildren: function (childrenData) {
                    childrenCount = childrenData.length;
                    childrenData.forEach(function (childData) {
                        verifyChild({
                            "text": childData.object,
                            "id": childData.object,
                            "a_attr": { href: "/dataset/" + childData.object.toLowerCase(), target: "_blank" }
                        });
                    });
                }
            };
        }
    }

});
