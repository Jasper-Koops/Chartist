from django.views.generic import TemplateView


class TestGraphView(TemplateView):
    template_name = "test_graph.html"
