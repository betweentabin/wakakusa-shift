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

def debug_layout_19():
    """Debug layout 19 data structure"""
    rf = RequestFactory()
    request = rf.get('/cultivation/layouts/19/')
    request.GET = request.GET.copy()
    request.GET['layout'] = 19
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
            if context and 'floor_plan_data_json' in context:
                try:
                    data = json.loads(context['floor_plan_data_json'])
                    if isinstance(data, dict) and 'plots' in data:
                        plots = data['plots']
                        print(f"Number of plots: {len(plots)}")
                        
                        # Look for plots with crops
                        for i, plot in enumerate(plots):
                            if 'level_details' in plot:
                                for level in plot['level_details']:
                                    if level['status'] != 'empty':
                                        print(f"Plot {i+1} ({plot.get('shelf_number', 'unknown')}): Level {level['level']} has {level['crop_name']} (status: {level['status']})")
                                        break
                                else:
                                    continue  # This plot has no crops
                                break  # Found a plot with crops, stop checking this plot
                        
                        # Print details of first plot with level_details
                        if len(plots) > 0 and 'level_details' in plots[0]:
                            print(f"First plot level details:")
                            for level in plots[0]['level_details']:
                                print(f"  Level {level['level']}: {level['crop_name']} ({level['status']})")
                                
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}")
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
    debug_layout_19()