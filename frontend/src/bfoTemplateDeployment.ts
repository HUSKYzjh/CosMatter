import { bfoTaskFormation, type BfoFormationStation } from "./bfoTaskFormation";
import { fleetOrchestration, type FleetRouteState } from "./fleetOrchestration";
import type { ImportedBundle } from "./model";
import type { UiLocale } from "./fleetRegistry";

export interface BfoTemplateDeploymentEntry extends BfoFormationStation {
  routeState: FleetRouteState;
}

/**
 * Compare a launch-time BFO template with the mission route without turning a
 * planned station into an execution claim. Route state comes solely from the
 * registered mission state in the current bundle.
 */
export function bfoTemplateDeployment(templateId: string, bundle: ImportedBundle, locale: UiLocale): BfoTemplateDeploymentEntry[] {
  const routeStateByFleet = new Map(fleetOrchestration(bundle).map((entry) => [entry.fleet.id, entry.state]));
  return bfoTaskFormation(templateId, locale).map((station) => ({ ...station, routeState: routeStateByFleet.get(station.fleetId) ?? "standby" }));
}
