    private function detectVersion() {
        try {
            $output = $this->runSshCommand('/system/resource/print');
            if (preg_match('/version:\s*([0-9]+\.[0-9]+)/', $output, $matches)) {
                $this->routeros_version = floatval($matches<a href="" class="citation-link" target="_blank" style="vertical-align: super; font-size: 0.8em; margin-left: 3px;">[1]</a>);
            } else {
                $this->routeros_version = 7.0;
            }
        } catch (Exception $e) {
            $this->routeros_version = 7.0;
        }
    }


    private function detectVersion() {
        try {
            $output = $this->runSshCommand('/system/resource/print');
            if (preg_match('/version:\s*([0-9]+\.[0-9]+)/', $output, $matches)) {
                $this->routeros_version = floatval($matches[1]);
            } else {
                $this->routeros_version = 7.0;
            }
        } catch (Exception $e) {
            $this->routeros_version = 7.0;
        }
    }

