import { useEffect, useState } from 'react';
import type { Vehicle } from '@/lib/format';

type Props = { vehicle: Vehicle; compact?: boolean };

export function VehicleCard({ vehicle, compact }: Props) {
  const [label, setLabel] = useState('');
  useEffect(() => { setLabel(vehicle.plate.toUpperCase()); }, [vehicle]);
  return <div>{compact ? vehicle.id : label}</div>;
}
