import { useService } from "@web/core/utils/hooks";

/**
 * Retourne:
 *  - state: réactif (useState(...)) -> rerender auto
 *  - actions: les méthodes exposées par le service (ex: selectRoom)
 *
 * Utilisation:
 *   const { state, actions } = useStore();
 *   const { rooms } = state; // rooms = state.rooms.list ...
 *   actions.selectRoom(id);
 */
export function useStore() {
  const store = useService("hm_reception_store");
  return {
    state: store.state,
    actions: store.actions,
    getters: store.getters,
  };
}
