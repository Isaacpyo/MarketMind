import type { components, operations } from "./schema";

type Schemas = components["schemas"];

export type Product = Schemas["Product"];
export type ProductPage = Schemas["ProductPage"];
export type Category = Schemas["Category"];
export type User = Schemas["User"];
export type AuthOut = Schemas["AuthOut"];
export type Recommendation = Schemas["Recommendation"];
export type RecommendationList = Schemas["RecommendationList"];
export type Strategy = RecommendationList["strategy"];
export type Cart = Schemas["Cart"];
export type CartLine = Schemas["CartLine"];
export type Order = Schemas["Order"];
export type Health = Schemas["Health"];
export type AdminOverview = Schemas["AdminOverview"];
export type TrainingRun = Schemas["TrainingRun"];
export type AlsParams = Schemas["AlsParams"];
export type ModelMetrics = Schemas["ModelMetrics"];
export type EventIn = Schemas["EventIn"];
type ProductQuery = NonNullable<operations["list_products_api_products_get"]["parameters"]["query"]>;
export type SortOption = NonNullable<ProductQuery["sort"]>;
