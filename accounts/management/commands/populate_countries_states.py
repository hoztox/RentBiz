from django.core.management.base import BaseCommand
from accounts.models import Country, State
import pycountry

class Command(BaseCommand):
    help = 'Populates the database with all countries and their corresponding states from pycountry'

    def handle(self, *args, **kwargs):
        # Counter for tracking created records
        country_count = 0
        state_count = 0

        # Iterate through all countries in pycountry
        for country in pycountry.countries:
            # Create or get the country
            country_obj, created = Country.objects.get_or_create(
                name=country.name,
                defaults={'code': country.alpha_2}
            )
            if created:
                country_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created country: {country.name} ({country.alpha_2})'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Country already exists: {country.name} ({country.alpha_2})'))

            # Get subdivisions (states, provinces, etc.) for the country
            try:
                subdivisions = pycountry.subdivisions.get(country_code=country.alpha_2)
                for subdivision in subdivisions:
                    # Create or get the state
                    state, created = State.objects.get_or_create(
                        name=subdivision.name,
                        country=country_obj
                    )
                    if created:
                        state_count += 1
                        self.stdout.write(self.style.SUCCESS(f'  Created state: {subdivision.name} in {country.name}'))
                    else:
                        self.stdout.write(self.style.SUCCESS(f'  State already exists: {subdivision.name} in {country.name}'))
            except LookupError:
                self.stdout.write(self.style.WARNING(f'No subdivisions found for {country.name}'))

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'Population complete: {country_count} countries and {state_count} states created.'
        ))