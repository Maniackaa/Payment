from datetime import timedelta

import pandas as pd
from django.contrib.auth import get_user_model

from payment.models import Work
User = get_user_model()

def work_calc():
    # Подсчет времени работы опера
    opers_work_calc = {}
    for user in User.objects.filter(is_staff=True):
        print(user)
        works = Work.objects.filter(user_id=user.id).all()
        if works:
            df = pd.DataFrame(list(works.values()))
            df.columns = ['pk', 'user_id', 'timestamp', 'status']
            # df['timestamp'] = pd.to_datetime(df['change_time'])
            print(df)

            result = []

            # Инициализируем переменные
            current_start = None

            for index, row in df.iterrows():
                if row['status'] == 1:
                    if current_start is None:
                        current_start = row['timestamp']
                else:
                    if current_start is not None:
                        # Если статус изменился на 0, фиксируем временной промежуток
                        result.append((current_start, row['timestamp']))
                        current_start = None

            # Если статус был равен 1 до конца данных
            if current_start is not None:
                result.append((current_start, df['timestamp'].iloc[-1]))

            # Подсчитываем время, когда статус был равен 1 за каждый день
            time_per_day = {}

            for start, end in result:
                while start < end:
                    day_start = start.normalize()  # Начало дня
                    day_end = (day_start + timedelta(days=1))  # Конец дня

                    # Определяем фактические границы для текущего дня
                    effective_start = max(start, day_start)
                    effective_end = min(end, day_end)

                    if effective_start < effective_end:
                        duration = effective_end - effective_start
                        if day_start not in time_per_day:
                            time_per_day[day_start] = timedelta()
                        time_per_day[day_start] += duration
                    start = day_end

            # Выводим результаты
            for day, duration in time_per_day.items():
                print(f"{day.date()}: {duration}")

            opers_work_calc[user.username] = time_per_day

    print(opers_work_calc)
    return opers_work_calc
