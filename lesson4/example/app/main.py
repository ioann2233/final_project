from database.config import get_settings
from database.database import get_session, init_db, get_database_engine
from services.crud.user import get_all_users, create_user
from sqlmodel import Session
from models.event import Event
from models.user import User


if __name__ == "__main__":
    settings = get_settings()
    print(settings.APP_NAME)
    print(settings.API_VERSION)
    print(f'Debug: {settings.DEBUG}')
    
    print(settings.DB_HOST)
    print(settings.DB_NAME)
    print(settings.DB_USER)
    
    init_db(drop_all=True)
    print('Init db has been success')
    
    test_user = User(email='test1@gmail.com', password='test')
    test_user_2 = User(email='test2@gmail.com', password='test')
    test_user_3 = User(email='test3@gmail.com', password='test')
    
    test_event = Event(title='test', image='test', description='test')
    test_event_2 = Event(title='test', image='test', description='test')
    
    test_user.events.append(test_event)
    test_user.events.append(test_event_2)
    
    engine = get_database_engine()
    
    with Session(engine) as session:
        create_user(test_user, session)
        create_user(test_user_2, session)
        create_user(test_user_3, session)
        users = get_all_users(session)
        
    print('-------')
    print(f'Id локального пользователя: {id(test_user)}')
    print(f'Id пользователя из БД: {id(users[0])}')
    print(f'Id одинаковые: {id(test_user) == id(users[0])}')

    print('-------')
    print('Пользователи из БД:')        
    for user in users:
        print(user)
        print('Пользовательские события:')
        if user.event_count == 0:
            print('Пользователь не имеет событий')
        else:
            for event in user.events:
                print(event)

