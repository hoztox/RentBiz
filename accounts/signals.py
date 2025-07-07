# your_app/signals.py
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django.utils import timezone

@receiver(post_migrate)
def setup_periodic_tasks(sender, **kwargs):
    """
    Setup periodic tasks after migrations are complete
    """
    print(f"Signal received for app: {sender.name}")
    if sender.name == 'accounts':


        # Create a daily schedule
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every= 1 ,
            period=IntervalSchedule.DAYS,
        )

        # Create or update the task
        PeriodicTask.objects.update_or_create(
            name='Generate Automated Invoices - Daily',
            defaults={
                'interval': schedule,
                'task': 'accounts.tasks.generate_automated_invoices',
                'description': 'Daily task to generate automated invoices',
                'enabled': True,
                'start_time': timezone.now(),
            }
        )
