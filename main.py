#imports
from choosing import *
from module import *
import streamlit as st
from PIL import Image
from datetime import date, timedelta


if 'sidebar_state' not in st.session_state:
    st.session_state['sidebar_state'] = 'expanded'

st.set_page_config(page_title="Choosing: enjoy your best meal",
                   page_icon="🔍",
                   layout="wide",
                   initial_sidebar_state=st.session_state["sidebar_state"],
                   menu_items={
                       'Get Help': "mailto:aless.ciocchetti@gmail.com",
                       'Report a bug': 'mailto:aless.ciocchetti@gmail.com',
                       'About': """
                       ## FAQ

                       ##### 1) Perchè il filtro sul tipo di pasto o sulla spesa per persona non cambia il ristorante consigliato?

                       Nel caso di risultato non derivante da un match con altri utenti, quei due filtri non vengono applicati.
                       Il consiglio infatti prende in considerazione solo le recensioni Google per la posizione ricercata.

                       ##### 2) Perchè non vedo più alcuni ristoranti che avevo nella mia lista ancora da valutare?

                       Hai 10 giorni di tempo dal momento in cui scegli un ristorante per lasciare una valutazione.
                       Dopodiché quel ristorante sarà rimosso dalla lista.

                       """

                        }
                   )

image = Image.open('logo.png')
st.image(image, width=450)

#inputs

st.sidebar.title(':mag::mag_right:')

username = st.sidebar.text_input('Identificati con una tua mail (non sarà visibile agli altri utenti)', placeholder="e.g. iamcool@coolest.it" ).strip().lower()

if not username:
    st.markdown("""
<div style = "text-align: justify;">


**Per cominciare, identificati con una mail nel menù a sinistra e buon appetito :)**


# Cos'è Choosing?

La sua missione unica e imprescindibile è quella di generare un consiglio personalizzato per il tuo prossimo ristorante.
Finalmente, non dovrai più scrivere a Pippo  *"Oh Pippo sono a Roma, dimmi dove posso andare a mangiare un'ottima pizza*", perchè la risposta te la da Choosing, che è molto più disponibile e preciso di Pippo.
E basta anche con le ore spese davanti ai siti di recensioni a contare le stelline e a confrontare prezzi e numero di commenti delle infinite alternative per poi
finire a mangiare nella solita osteria.

Dedica il tuo tempo alle cose migliori. A sceglierle ci pensa Choosing.

Enjoy your best meal.


## Come funziona?

Choosing usa due strategie alternative:

 1. Ricerca per similarità tra gli utenti di Choosing in base ai ristoranti in comune e ai rating assegnati

 2. Qualora 1. non restituisca un risultato, Choosing sceglie il ristorante migliore basandosi sulle recensioni di Google

Il consiglio che deriva da 1. è molto più personalizzato rispetto a quello di 2. ed è il vero orgoglio di Choosing. L'unica condizione affinché si verifichi è la partecipazione attiva di tanti utenti e il passaparola, se credi nei superpoteri di Choosing.



## Feedback

Per suggerimenti o per rimanere semplicemente in contatto scrivimi a aless.ciocchetti@gmail.com


## Support

Mantenere e migliorare Choosing ha qualche costo (APIs, server...).

Se credi che Choosing sia una bella e utile idea, puoi sostenerla con una piccola donazione qua: [Buy me a coffee](https://www.buymeacoffee.com/palealex)


## Author

- [Alessandro Ciocchetti](https://www.linkedin.com/in/ac-palealex/)


## 🚀 About Me
Gestisco il mio tempo tra tentativi di scrivere qualcosa che somigli a bel codice, di sviluppare idee che ricordino grandi progetti, di suonare l'armonica come la suonava Paul Butterfield.

Lo sviluppo web e lo studio delle proprietà delle Serie Temporali mi divertono particolarmente.

</div>

""", unsafe_allow_html=True)

elif not check(username): #and username != config.root:
    st.warning('Email non valida', icon="⚠️")

#elif username == config.root:
#    with open('final.csv') as f:
#        st.download_button('final', f, mime='text/csv')
#    with open('suggests.csv') as f:
#        st.download_button('suggests', f, mime='text/csv')
#    canc = st.checkbox("cancella file temporanei")
#    mydir = "user_temps/"
#    filelist = [ f for f in os.listdir(mydir) if f.endswith(".csv") ]
#    st.write("numero file temporanei esistenti ", len(filelist))
#    to_delete = st.multiselect('Delete', filelist, filelist)

#    if canc:
#        for f in to_delete:
#            os.remove(os.path.join(mydir, f))
#            st.write(f)
    #mettere anche funzione per cancellare da final delle righe di utenti sbagliati per esempio (deve diventare dashboard di controllo)

else:
    with st.sidebar:
        st.markdown(f'''

        <small>Benvenuto {username}!</small>
        <small>Utilizza sempre questa mail per accedere al tuo account.</small>

        <small>Inserisci le informazioni geografiche qui sotto per conoscere il miglior ristorante per te</small>
        ''', unsafe_allow_html=True)
        with st.form(key='search'):
            city = st.text_input('Città', placeholder="e.g. Ferrara", key = "field").capitalize()
            province = st.text_input('Provincia (sigla)', placeholder="e.g. FE", max_chars=2).upper()
            state = "Italia" #st.text_input('Stato', placeholder="e.g. Italia").capitalize()
            border = st.selectbox("Confine di ricerca", ("comune", "provincia"))
            submitted = st.form_submit_button("Aggiorna")
            st.write('*<small>(la modifica dei campi seguenti influenza il consiglio solo se esiste un match con altri utenti)</small>*', unsafe_allow_html=True )
            meal = st.multiselect('Cosa vuoi mangiare?', ("Primi piatti", "Pizza", "Street food", "Carne", "Pesce", "Vegetariano/Vegano", "Etnico", "Orientale", "Altro"), ("Primi piatti", "Pizza", "Street food", "Carne", "Pesce", "Vegetariano/Vegano", "Etnico", "Orientale", "Altro"), help="Utile solo nel caso di ricerca per similarità con altri utenti")
            epp = st.slider("Range spesa per persona", 1, 100, (15, 50), help="Utile solo nel caso di ricerca per similarità con altri utenti")
            st.write("  ")
        if submitted:
            st.session_state['sidebar_state']  = 'collapsed' if st.session_state['sidebar_state']  == 'expanded' else 'expanded'
            st.experimental_rerun()


    if not meal or not city or not province:
        st.write("*Per conoscere il tuo prossimo miglior ristorante, compila i campi del menù laterale. Se invece devi ancora valutare un ristorante in cui sei stato, continua prima qui sotto*")

        #reviewing

        container1 = st.expander("VEDI I RISTORANTI A CUI POTRESTI LASCIARE UNA VALUTAZIONE")
        with container1:
            user_to_review = read_suggests()
            user_to_review = user_to_review[user_to_review["user"] == username].drop_duplicates(keep= 'last').reset_index(drop= True)

            if len(user_to_review) > 0:
                st.dataframe(data=user_to_review.iloc[:, :-1])

                with st.form(key="review"):
                    selected = st.selectbox("Selezionane uno dalla lista", set(user_to_review["name"]))
                    reviewed = user_to_review[user_to_review["name"] == selected].reset_index(drop = True)

                    NUMBER_OF_COLUMNS = 3
                    f, s, t = st.columns(NUMBER_OF_COLUMNS)
                    with f:
                        reviewed_meal = st.selectbox("Cos'hai mangiato? (se hai provato diverse portate, seleziona quella che ti ha convinto maggiormente)", ("Primi piatti", "Pizza", "Street food", "Carne", "Pesce", "Vegetariano/Vegano", "Etnico", "Orientale", "Altro"))
                    with s:
                        reviewed_epp = st.slider('Spesa per persona (circa)', 1, 100, 25)
                    with t:
                        reviewed_rate = st.slider('Valutazione complessiva', 1.0, 10.0, 8.0, 0.1)
                    ok = st.form_submit_button("Invia!")

                if ok:
                    st.balloons()
                    st.success("Grazie per il tuo contributo. Continua a usare Choosing :) ", icon = "✅")
                    reviewed["added"] = datetime.date(datetime.now())
                    reviewed["rate"] = reviewed_rate
                    reviewed["what"] = reviewed_meal.capitalize()
                    reviewed["epp"] = reviewed_epp

                    final = read_final()

                    final = pd.concat([final, reviewed], axis=0, ignore_index=True)
                    final = final.drop_duplicates(subset=["name", "user", "what"], keep = 'last').reset_index(drop=True)
                    final.to_csv("final.csv")
                    filename = "final.csv"
                    upload(filename)

                    tendaysago = date.today() - timedelta(10)
                    suggests = read_suggests().reset_index(drop=True)

                    suggests["added"] = pd.to_datetime(suggests["added"], format='%Y-%m-%d').dt.date

                    try:
                        suggests.drop(suggests.index[(suggests['name'] == reviewed['name'][0]) & (suggests['user'] == reviewed['user'][0])], inplace=True)
                    except:
                        pass
                    suggests = suggests[suggests["added"] > tendaysago].reset_index(drop=True)
                    suggests.to_csv("suggests.csv")
                    filename = "suggests.csv"
                    upload(filename)

                    st.experimental_rerun()

            else:
                st.write("Non hai nessun ristorante salvato da valutare. Scegline prima uno e, dopo averlo provato, torna qua a valutarlo.")

        container2 = st.expander("VEDI I RISTORANTI A CUI HAI LASCIATO UNA VALUTAZIONE")
        with container2:
            user_reviewed = read_final()
            user_reviewed = user_reviewed[user_reviewed["user"] == username].drop_duplicates(keep= 'last').reset_index(drop= True)

            if len(user_reviewed) > 0:
                st.dataframe(data=user_reviewed.iloc[:, [0,1,3,5,6,7]])
            else:
                st.write("Non hai ancora lasciato nessuna valutazione.")
    else:
        #choosing object
        ch = Choosing(username, meal, city, province, state, epp, border)
        df = (
            ch.read_temp()[0:0]
            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
        )
        filename = f"user_temps/temp_{username}.csv"
        upload(filename)

        #suggests

        container = st.expander("TI SVELO IL TUO PROSSIMO MIGLIOR RISTORANTE")
        with container:
            #---------------------------------------------------------------------
            def markdown_and_save(n_rist, type_of_choice):
                if type_of_choice == 'matched':
                    chose = ch.matched_choice(choice = n_rist)
                    st.markdown('''
                        ******Trovato :tada: ! In base al match con gli altri utenti:******

                        *(se sei già stato in tutte le proposte di Choosing prova a modificare i criteri di ricerca, oppure torna nel migliore e assaggia qualcosa di nuovo!)*
                        ''')
                else:
                    chose, latlon = ch.random_choice(choice = n_rist)

                    st.markdown('''
                            ******Non ci sono suggerimenti per questa zona in base a similarità con altri utenti. Ecco uno dei migliori ristoranti selezionato secondo le recensioni di Google:******
                            ''')
                    st.map(latlon, zoom = 13)

                html_str = f"""
                                <div style ="text-align: center;" >
                                    <h3>
                                        {chose.iloc[:,0][0]}
                                    </h3>
                                    <h6>
                                        {chose.iloc[:,1][0]}
                                        <br>
                                    </h6>
                                </div>
                                <br>
                                """
                return html_str, chose

            #--------------------------------------------------------------------

            try:
                alt = len(ch.matched_suggests())
                if alt == 1:
                    n_rist = 0
                    html, chose = markdown_and_save(n_rist, type_of_choice="matched")
                    st.markdown(html, unsafe_allow_html=True)
                    form = st.form(key="case1", clear_on_submit = True)
                    with form:
                        ok = st.checkbox("Ok, scelgo questo!")
                    submit = form.form_submit_button("Salva")
                    if submit:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")

                        suggests = read_suggests()

                        suggests = pd.concat([suggests, chose], axis = 0, ignore_index=True)
                        suggests.to_csv("suggests.csv")
                        filename = "suggests.csv"
                        upload(filename)

                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        filename = f"user_temps/temp_{username}.csv"
                        upload(filename)

                elif alt > 1:
                    already = st.checkbox("Ci sono già stato, dimmene un altro")
                    if already:
                        disabled = False
                    else:
                        disabled = True

                    rist_slider = st.select_slider(
                        'Ecco delle alternative in ordine decrescente di punteggio di match',
                        options=np.arange(1, alt+1, 1), disabled = disabled)

                    n_rist = rist_slider - 1
                    html, chose = markdown_and_save(n_rist, type_of_choice="matched")

                    st.markdown(html, unsafe_allow_html=True)
                    form = st.form(key="case2", clear_on_submit = True)
                    with form:
                        ok = st.checkbox("Ok, scelgo questo!")
                    submit = form.form_submit_button("Salva")
                    if submit:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")

                        suggests = read_suggests()

                        suggests = pd.concat([suggests, chose], axis=0, ignore_index=True)
                        suggests.to_csv("suggests.csv")
                        filename = "suggests.csv"

                        upload(filename)

                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        filename = f"user_temps/temp_{username}.csv"

                        upload(filename)

                else:
                    raise Exception("Nessun match trovato")

            except:
                try:
                    if border == 'provincia':
                        alt = 0
                        while alt == 0:
                            alt = len(ch.random_restaurants()) #se non trova niente nella provincia, rifa un altro giro
                    else:
                        alt = len(ch.random_restaurants())

                    if alt == 1:
                        n_rist = 0
                        html, chose = markdown_and_save(n_rist, type_of_choice="random")
                        st.markdown(html, unsafe_allow_html=True)

                        form = st.form(key="case3", clear_on_submit = True)
                        with form:
                            ok = st.checkbox("Ok, scelgo questo!")
                        submit = form.form_submit_button("Salva")
                        if submit:
                            st.balloons()
                            st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")

                            suggests = read_suggests()

                            suggests = pd.concat([suggests, chose], axis=0, ignore_index=True)
                            suggests.to_csv("suggests.csv")
                            filename = "suggests.csv"

                            upload(filename)

                            df = (
                                ch.read_temp()[0:0]
                                .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                            )
                            filename = f"user_temps/temp_{username}.csv"

                            upload(filename)


                    elif alt > 1:
                        already = st.checkbox("Ci sono già stato, dimmene un altro")
                        if already:
                            disabled = False
                        else:
                            disabled = True
                        rist_slider = st.select_slider(
                            'Ecco delle alternative in ordine decrescente di punteggio calcolato in base alle recensioni di Google',
                            options=np.arange(1, alt+1, 1), disabled = disabled)
                        n_rist = rist_slider - 1

                        html, chose = markdown_and_save(n_rist, type_of_choice="random")
                        st.markdown(html, unsafe_allow_html=True)

                        form = st.form(key="case4", clear_on_submit = True)
                        with form:
                            ok = st.checkbox("Ok, scelgo questo!")
                        submit = form.form_submit_button("Salva")
                        if submit:
                            st.balloons()
                            st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")

                            suggests = read_suggests()

                            suggests = pd.concat([suggests, chose], axis=0, ignore_index=True)
                            suggests.to_csv("suggests.csv")

                            filename = "suggests.csv"
                            upload(filename)

                            df = (
                                ch.read_temp()[0:0]
                                .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                            )
                            filename = f"user_temps/temp_{username}.csv"

                            upload(filename)

                    if alt == 0:
                        st.write("Nessun consiglio per i criteri ricercati.")

                except:
                    st.write("La ricerca non è andata a buon fine... Verifica che le informazioni nei campi da te inserite siano coerenti, o prova a reimpostare la ricerca.")
