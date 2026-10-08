import { VehicleCard } from '@/components/VehicleCard';
import { plate } from '@/lib/format';

export const App = () => <VehicleCard vehicle={{ id: 1, plate: plate('ab 12') }} />;
