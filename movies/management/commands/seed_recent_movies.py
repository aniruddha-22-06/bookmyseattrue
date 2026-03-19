from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from movies.models import Genre, Language, Movie, Theater, Seat


class Command(BaseCommand):
    help = 'Seed recent movies with theaters and seats'

    def handle(self, *args, **options):
        remove_titles = [
            'Dune',
            'The Dark Knight',
            'Titanic',
            'Avatar',
            'Bahubali: The Beginning',
            'Bahubali 2: The Conclusion',
            'KGF: Chapter 1',
            'KGF: Chapter 2',
        ]
        Movie.objects.filter(name__in=remove_titles).delete()

        language_codes = {
            'Hindi': 'hi',
            'Telugu': 'te',
            'English': 'en',
        }
        movies_data = [
            (
                'Pushpa 2: The Rule',
                'movies/635217f73e372771013edb4c-the-avengers-poster-marvel-movie-canvas1.jpg',
                8.4,
                'Allu Arjun, Rashmika Mandanna',
                'Action drama sequel',
                'https://www.youtube.com/watch?v=g3JUbgOHgdw',
                'https://upload.wikimedia.org/wikipedia/en/1/11/Pushpa_2-_The_Rule.jpg',
                ['Action', 'Drama'],
                ['Hindi', 'Telugu'],
            ),
            (
                'Devara Part 1',
                'movies/feUv2SYumXlT8E2RhzlYbZxfEGLG5AVrCPxP1gmAaCusxyPnA1.jpg',
                7.8,
                'NTR Jr, Janhvi Kapoor',
                'Coastal action drama',
                'https://www.youtube.com/watch?v=rc61YHl1PFY',
                'https://upload.wikimedia.org/wikipedia/en/f/f0/Devara_Part_1.jpg',
                ['Action', 'Drama'],
                ['Telugu', 'Hindi'],
            ),
            (
                'Kalki 2898 AD',
                'movies/f5VK0h2bprRhR6iRrixcuEfRxSUF4l14F66vQYrsJGmKZ5nTA1.jpg',
                8.2,
                'Prabhas, Deepika Padukone',
                'Sci-fi action spectacle',
                'https://www.youtube.com/watch?v=y1-w1kUGuz8',
                'https://upload.wikimedia.org/wikipedia/en/4/4c/Kalki_2898_AD.jpg',
                ['Sci-Fi', 'Action'],
                ['Hindi', 'Telugu'],
            ),
            (
                'Stree 2',
                'movies/IQsBhg9t747dLhjXfsChIGZy4XfugER8BF0Gw5MDhIcnY5nTA1.jpg',
                8.1,
                'Rajkummar Rao, Shraddha Kapoor',
                'Horror comedy sequel',
                'https://www.youtube.com/watch?v=KVnheXywIbY',
                'https://upload.wikimedia.org/wikipedia/en/a/a1/Stree_2.jpg',
                ['Horror', 'Comedy'],
                ['Hindi'],
            ),
            (
                'Fighter',
                'movies/download.jpeg',
                7.5,
                'Hrithik Roshan, Deepika Padukone',
                'Aerial action entertainer',
                'https://www.youtube.com/watch?v=6amIq_mP4xM',
                'https://upload.wikimedia.org/wikipedia/en/d/df/Fighter_film_teaser.jpg',
                ['Action', 'Thriller'],
                ['Hindi'],
            ),
            (
                'Avengers',
                'movies/download.jpeg',
                8.0,
                'Robert Downey Jr., Chris Evans',
                'Superhero team-up blockbuster',
                'https://www.youtube.com/watch?v=eOrNdBpGMv8',
                'https://upload.wikimedia.org/wikipedia/en/8/8a/The_Avengers_%282012_film%29_poster.jpg',
                ['Action', 'Sci-Fi'],
                ['English'],
            ),
            (
                'Avengers: Endgame',
                'movies/download.jpeg',
                8.4,
                'Robert Downey Jr., Chris Evans',
                'Epic conclusion to the saga',
                'https://www.youtube.com/watch?v=TcMBFSGVi1c',
                'https://upload.wikimedia.org/wikipedia/en/0/0d/Avengers_Endgame_poster.jpg',
                ['Action', 'Sci-Fi'],
                ['English'],
            ),
            (
                'Inception',
                'movies/download.jpeg',
                8.8,
                'Leonardo DiCaprio, Joseph Gordon-Levitt',
                'Mind-bending heist thriller',
                'https://www.youtube.com/watch?v=YoHD9XEInc0',
                'https://upload.wikimedia.org/wikipedia/en/2/2e/Inception_%282010%29_theatrical_poster.jpg',
                ['Sci-Fi', 'Thriller'],
                ['English'],
            ),
            (
                'Interstellar',
                'movies/download.jpeg',
                8.6,
                'Matthew McConaughey, Anne Hathaway',
                'Space exploration drama',
                'https://www.youtube.com/watch?v=zSWdZVtXT7E',
                'https://upload.wikimedia.org/wikipedia/en/b/bc/Interstellar_film_poster.jpg',
                ['Sci-Fi', 'Drama'],
                ['English'],
            ),
            (
                'Joker',
                'movies/download.jpeg',
                8.5,
                'Joaquin Phoenix, Robert De Niro',
                'Psychological character study',
                'https://www.youtube.com/watch?v=zAGVQLHvwOY',
                'https://upload.wikimedia.org/wikipedia/en/e/e1/Joker_%282019_film%29_poster.jpg',
                ['Drama', 'Thriller'],
                ['English'],
            ),
            (
                'Spider-Man',
                'movies/download.jpeg',
                7.9,
                'Tom Holland, Zendaya',
                'Superhero coming-of-age',
                'https://www.youtube.com/watch?v=JfVOs4VSpmA',
                'https://upload.wikimedia.org/wikipedia/en/0/00/Spider-Man_No_Way_Home_poster.jpg',
                ['Action', 'Sci-Fi'],
                ['English'],
            ),
            (
                'Oppenheimer',
                'movies/download.jpeg',
                8.6,
                'Cillian Murphy, Emily Blunt',
                'Biographical drama',
                'https://www.youtube.com/watch?v=uYPbbksJxIg',
                'https://upload.wikimedia.org/wikipedia/en/4/4a/Oppenheimer_%28film%29.jpg',
                ['Drama', 'Thriller'],
                ['English'],
            ),
            (
                'RRR',
                'movies/download.jpeg',
                8.0,
                'NTR Jr, Ram Charan',
                'Action drama spectacle',
                'https://www.youtube.com/watch?v=NgBoMJy386M',
                'https://upload.wikimedia.org/wikipedia/en/d/d7/RRR_Poster.jpg',
                ['Action', 'Drama'],
                ['Telugu', 'Hindi'],
            ),
        ]

        created_movies = 0
        for idx, (name, image, rating, cast, description, trailer_url, poster_url, genres, languages) in enumerate(movies_data, start=1):
            movie, created = Movie.objects.get_or_create(
                name=name,
                defaults={
                    'image': image,
                    'rating': rating,
                    'cast': cast,
                    'description': description,
                    'trailer_url': trailer_url,
                    'metadata': {'poster_url': poster_url},
                },
            )
            if not created:
                movie.image = image
                movie.rating = rating
                movie.cast = cast
                movie.description = description
                movie.trailer_url = trailer_url
                metadata = movie.metadata or {}
                metadata['poster_url'] = poster_url
                movie.metadata = metadata
                movie.save(update_fields=['image', 'rating', 'cast', 'description', 'trailer_url', 'metadata'])
            else:
                created_movies += 1

            genre_objs = []
            for genre_name in genres:
                genre_obj, _ = Genre.objects.get_or_create(
                    name=genre_name,
                    defaults={'slug': genre_name.lower().replace(' ', '-')},
                )
                genre_objs.append(genre_obj)
            movie.genres.set(genre_objs)

            language_objs = []
            for language_name in languages:
                language_obj, _ = Language.objects.get_or_create(
                    name=language_name,
                    defaults={'code': language_codes.get(language_name, language_name[:2].lower())},
                )
                language_objs.append(language_obj)
            movie.languages.set(language_objs)

            theater, _ = Theater.objects.get_or_create(
                name=f'PVR Screen {idx}',
                movie=movie,
                defaults={'show_time': timezone.now() + timedelta(hours=idx * 2)},
            )

            for seat_no in range(1, 41):
                Seat.objects.get_or_create(theater=theater, seat_number=f'A{seat_no}')
        trailer_backfill = {
            'Avengers': 'https://www.youtube.com/watch?v=eOrNdBpGMv8',
            'Avengers: Endgame': 'https://www.youtube.com/watch?v=TcMBFSGVi1c',
            'Inception': 'https://www.youtube.com/watch?v=YoHD9XEInc0',
            'Interstellar': 'https://www.youtube.com/watch?v=zSWdZVtXT7E',
            'Joker': 'https://www.youtube.com/watch?v=zAGVQLHvwOY',
            'Spider-Man': 'https://www.youtube.com/watch?v=JfVOs4VSpmA',
        }
        for movie_name, trailer_url in trailer_backfill.items():
            Movie.objects.filter(name=movie_name).update(trailer_url=trailer_url)
        self.stdout.write(self.style.SUCCESS(f'Recent movies seeded. Created new movies: {created_movies}'))

