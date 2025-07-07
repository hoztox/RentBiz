# tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from company.views import AutoGenerateInvoiceAPIView
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def generate_automated_invoices(self):
    """
    Celery task to generate automated invoices for all active configurations
    """
    try:
        logger.info("Starting automated invoice generation task")
        
        # Create an instance of the API view
        view = AutoGenerateInvoiceAPIView()
        print("AutoGenerateInvoiceAPIView instance created")
        
        # Call the generate_invoices method
        results = view.generate_invoices()
        
        logger.info(f"Automated invoice generation completed. Results: {results}")
        return {
            'success': True,
            'message': 'Automated invoice generation completed',
            'results': results
        }
    except Exception as e:
        logger.error(f"Error in automated invoice generation task: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': f'Failed to generate invoices: {str(e)}'
        }
