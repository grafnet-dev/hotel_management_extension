import { RoomStore } from "./rooms";
import { UserStore } from "./user";
import { ReservationStore } from "./reservations";
import { UIStore } from "./ui";

export const AppState = {
    rooms: RoomStore,
    user: UserStore,
    reservations: ReservationStore,
    ui: UIStore,
};
