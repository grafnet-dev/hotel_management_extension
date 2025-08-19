import { RoomStore } from "./rooms";
import { UserStore } from "./user";
import { ReservationStore } from "./reservations";
import { ClientStore } from "./clients";
import { ProductStore } from "./products";
import { EventsStore } from "./events";
import { ServicesStore } from "./services";
import {PoliceFormStore} from "./police_form";
import { UIStore } from "./ui";


export const AppState = {
    rooms: RoomStore,
    user: UserStore,
    reservations: ReservationStore,
    ui: UIStore,
    clients: ClientStore,
    products: ProductStore,
    events: EventsStore,
    services: ServicesStore,
    police_forms: PoliceFormStore,
};
