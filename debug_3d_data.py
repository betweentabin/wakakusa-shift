#!/usr/bin/env python
import os
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from cultivation.views import plot_grid_view
from django.test import RequestFactory
from django.contrib.auth.models import User

def debug_3d_data():
    """Debug 3D data structure"""
    rf = RequestFactory()
    request = rf.get('/cultivation/layouts/17/')
    request.GET = request.GET.copy()
    request.GET['layout'] = 17
    request.GET['mode'] = 'floor_plan'
    request.GET['display'] = 'auto'
    
    # Add a test user
    user = User.objects.first()
    if user:
        request.user = user
        
        # Monkey patch the render method to intercept context
        from django.shortcuts import render
        original_render = render
        
        def debug_render(request, template_name, context=None, *args, **kwargs):
            print(f"Template: {template_name}")
            if context:
                if 'floor_plan_data_json' in context:
                    print("floor_plan_data_json found in context")
                    try:
                        data = json.loads(context['floor_plan_data_json'])
                        print(f"Parsed JSON data structure: {type(data)}")
                        if isinstance(data, dict) and 'plots' in data:
                            plots = data['plots']
                            print(f"Number of plots: {len(plots)}")
                            if len(plots) > 0:
                                first_plot = plots[0]
                                print(f"First plot keys: {list(first_plot.keys())}")
                                if 'level_details' in first_plot:
                                    print(f"Level details found: {len(first_plot['level_details'])} levels")
                                    for i, level in enumerate(first_plot['level_details']):
                                        print(f"  Level {i+1}: {level}")
                                else:
                                    print("No level_details in first plot")
                        else:
                            print(f"Data structure: {data}")
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}")
                
                if 'floor_plan_data' in context:
                    print("floor_plan_data found in context")
                    data = context['floor_plan_data']
                    print(f"floor_plan_data type: {type(data)}")
                    if isinstance(data, dict) and 'plots' in data:
                        plots = data['plots']
                        print(f"Number of plots in raw data: {len(plots)}")
                        if len(plots) > 0:
                            first_plot = plots[0]
                            print(f"First plot keys in raw data: {list(first_plot.keys())}")
                            if 'level_details' in first_plot:
                                print(f"Level details in raw data: {first_plot['level_details']}")
            return original_render(request, template_name, context, *args, **kwargs)
        
        # Monkey patch render
        import cultivation.views
        cultivation.views.render = debug_render
        
        try:
            response = plot_grid_view(request)
            print('View executed successfully')
        except Exception as e:
            print(f'ERROR: {e}')
            import traceback
            traceback.print_exc()
        finally:
            # Restore original render
            cultivation.views.render = original_render
    else:
        print('No user found to test with')

if __name__ == "__main__":
    debug_3d_data()