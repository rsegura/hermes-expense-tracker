-- Test fixture only — not used by bootstrap.sh or production install.

INSERT OR IGNORE INTO persons (slug, display_name, aliases) VALUES
  ('alice', 'Alice', '["ali"]'),
  ('bob', 'Bob', '["bobby"]');

INSERT OR IGNORE INTO projects (slug, name, description) VALUES
  ('hogar', 'Hogar', 'Gastos del hogar');

INSERT OR IGNORE INTO categories (slug, name) VALUES
  ('comida', 'Comida'),
  ('supermercado', 'Supermercado'),
  ('restaurante', 'Restaurante'),
  ('transporte', 'Transporte'),
  ('salud', 'Salud'),
  ('farmacia', 'Farmacia'),
  ('impuestos', 'Impuestos'),
  ('servicios', 'Servicios'),
  ('alquiler', 'Alquiler'),
  ('hipoteca', 'Hipoteca'),
  ('mascotas', 'Mascotas'),
  ('hogar', 'Hogar'),
  ('viajes', 'Viajes'),
  ('tecnologia', 'Tecnología'),
  ('educacion', 'Educación');
