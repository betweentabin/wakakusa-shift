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

def debug_3d_layout_19():
    """Debug layout 19 3D data structure specifically"""
    rf = RequestFactory()
    request = rf.get('/cultivation/layouts/19/')
    request.GET = request.GET.copy()
    request.GET['layout'] = 19
    request.GET['mode'] = 'floor_plan'
    request.GET['display'] = 'plots'  # Force plots display to see 3D data
    
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
                        
                        # Look specifically for plot 77
                        for plot in plots:
                            plot_id = plot.get('id') or plot.get('plot', {}).get('id')
                            if plot_id == 77:
                                print(f"Found plot 77 data:")
                                print(f"  Shelf number: {plot.get('shelf_number', 'unknown')}")
                                if 'level_details' in plot:
                                    print(f"  Level details:")
                                    for level in plot['level_details']:
                                        print(f"    Level {level['level']}: {level['crop_name']} ({level['status']})")
                                else:
                                    print(f"  No level_details found")
                                    print(f"  Available keys: {list(plot.keys())}")
                                break
                        else:
                            print("Plot 77 not found in data")
                            # Show first few plots for debugging
                            for i, plot in enumerate(plots[:3]):
                                plot_id = plot.get('id') or plot.get('plot', {}).get('id')
                                shelf_number = plot.get('shelf_number', 'unknown')
                                print(f"  Plot {i+1} (ID: {plot_id}): {shelf_number}")
                                
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
    debug_3d_layout_19()