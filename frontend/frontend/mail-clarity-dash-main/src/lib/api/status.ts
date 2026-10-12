import type { Schemas } from "../../types/schema";
import { request } from "./client";

export type ServiceStatus = Schemas["ServiceStatus"];
export type PartState = ServiceStatus["parts"]["backend"];

/** Public: which part of AIMail works, nothing more (specs/features/todo-redesign-and-status.md). */
export const fetchServiceStatus = () => request<ServiceStatus>("/service-status");
