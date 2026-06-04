// Runs on first container start as root
db = db.getSiblingDB("adsignal");

db.createCollection("raw_creatives");
db.createCollection("brand_metadata");

// Compound index: brand + ingested_at for time-range queries
db.raw_creatives.createIndex(
  { brand: 1, ingested_at: -1 },
  { name: "brand_ingested_compound" }
);

// Index for source-dedup
db.raw_creatives.createIndex(
  { source_id: 1, source: 1 },
  { unique: true, name: "source_dedup", sparse: true }
);

// TTL index: auto-expire raw docs after 90 days (optional, remove for portfolio demo)
// db.raw_creatives.createIndex({ ingested_at: 1 }, { expireAfterSeconds: 7776000 });

db.brand_metadata.createIndex({ brand_slug: 1 }, { unique: true });

print("MongoDB: adsignal database and indexes created");
